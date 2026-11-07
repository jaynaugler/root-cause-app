import dotenv from 'dotenv';
// Load the shared workspace-root .env (../../ from web/src/scripts) regardless of cwd
dotenv.config({ path: new URL('../../../.env', import.meta.url) });
import { MongoClient } from 'mongodb';

// Keep these in sync with api/app/ai.py (CATEGORIES) and web/src/routes/pdf/+page.svelte —
// three layers must agree or fetches fail validation at insert.
const CATEGORIES = ['people', 'places', 'events', 'organizations', 'publications', 'history'];
// 'unapproved' is not used yet: everything is inserted 'approved' for now.
const STATUSES = ['pending', 'approved', 'unapproved'];

// resourceformat: only 'pdf' exists today, fetched by api/app/pdf.py.
// description: capped at 150 chars (card teaser) — the insert flow must slice
// longer raw text (fallback records with no Gemini summary) to stay valid.
const RESOURCE_SCHEMA = {
	bsonType: 'object',
	required: [
		'title',
		'link',
		'description',
		'summary',
		'attribution',
		'resourceformat',
		'contentcategory',
		'imgurl',
		'status',
		'createdAt'
	],
	properties: {
		_id: { bsonType: 'objectId' },
		title: { bsonType: ['string', 'null'], maxLength: 300 },
		link: { bsonType: 'string', pattern: '^https?://', maxLength: 2000 },
		// Optional (curator-supplied): the site page hosting the resource.
		sitelink: { bsonType: ['string', 'null'], pattern: '^https?://', maxLength: 2000 },
		description: { bsonType: ['string', 'null'], maxLength: 150 },
		// minLength applies to strings only; null (fallback records) is still valid.
		summary: { bsonType: ['string', 'null'], minLength: 250 },
		attribution: { bsonType: ['string', 'null'] },
		resourceformat: { bsonType: 'string', enum: ['pdf'] },
		contentcategory: { enum: [...CATEGORIES, null] },
		imgurl: { bsonType: ['string', 'null'] },
		status: { enum: STATUSES },
		createdAt: { bsonType: 'date' }
	},
	// details/raw and anything else the fetch pipeline adds stay out of Mongo:
	// the insert flow strips them BEFORE writing.
	additionalProperties: false
};

async function main() {
	const atlasUri = process.env.ATLAS_URI?.trim();
	const atlasDb = process.env.ATLAS_DB?.trim();
	const localUri = process.env.MONGODB_URI?.trim();
	const localDb = process.env.MONGODB_DB?.trim();

	let uri = '';
	let dbName = '';
	let target = '';

	if (atlasUri) {
		uri = atlasUri;
		dbName = atlasDb || localDb || 'root-cause_db';
		target = 'Atlas';
	} else if (localUri) {
		uri = localUri;
		dbName = localDb || 'root-cause_db';
		target = 'Local';
	} else {
		console.error('❌ Database configuration missing: Set ATLAS_URI or MONGODB_URI in .env');
		process.exit(1);
	}

	console.log(`🛡️  Applying resources schema validation on ${target} MongoDB (${dbName})...`);
	const client = new MongoClient(uri);

	try {
		await client.connect();
		const db = client.db(dbName);
		const exists = (await db.listCollections({ name: 'resources' }).toArray()).length > 0;

		if (exists) {
			await db.command({
				collMod: 'resources',
				validator: { $jsonSchema: RESOURCE_SCHEMA },
				validationLevel: 'strict',
				validationAction: 'error'
			});
			console.log('✅ Updated validation on the existing resources collection.');
		} else {
			await db.createCollection('resources', {
				validator: { $jsonSchema: RESOURCE_SCHEMA },
				validationLevel: 'strict',
				validationAction: 'error'
			});
			console.log('✅ Created the resources collection with schema validation.');
		}
	} catch (error) {
		console.error('❌ Schema validation setup failed:', error);
		process.exit(1);
	} finally {
		await client.close();
		console.log('🔌 Database connection closed.');
	}
}

main();
