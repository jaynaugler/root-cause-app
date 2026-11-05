import 'dotenv/config'; // Instantly loads your project root .env
import { MongoClient } from 'mongodb';

async function main() {
	const atlasUri = process.env.ATLAS_URI?.trim();
	const atlasDb = process.env.ATLAS_DB?.trim();
	const localUri = process.env.MONGODB_URI?.trim();
	const localDb = process.env.MONGODB_DB?.trim();

	let uri = '';
	let dbName = '';
	let target = '';

	// Mirror the fallback logic from your SvelteKit singleton
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

	console.log(`🌱 Connecting to ${target} MongoDB (${dbName})...`);
	const client = new MongoClient(uri);

	try {
		await client.connect();
		const db = client.db(dbName);
		const itemsCollection = db.collection('items');

		console.log('🗑️  Clearing existing items...');
		await itemsCollection.deleteMany({});

		console.log('📝 Inserting seed data...');
		const result = await itemsCollection.insertMany([
			{ name: 'Configure Webhooks', createdAt: new Date() },
			{ name: 'Draft API Endpoints', createdAt: new Date() },
			{ name: 'Verify Docker Containers', createdAt: new Date() }
		]);

		console.log(`✅ Successfully seeded ${result.insertedCount} documents!`);
	} catch (error) {
		console.error('❌ Seeding failed:', error);
		process.exit(1);
	} finally {
		await client.close();
		console.log('🔌 Database connection closed.');
	}
}

main();