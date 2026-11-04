// src/lib/server/db.ts
import { MongoClient, type Db } from 'mongodb';
import { ATLAS_URI, ATLAS_DB, MONGODB_URI, MONGODB_DB } from '$app/env/private';
import { dev } from '$app/env';

function resolveDbConfig() {
	const atlasUri = ATLAS_URI?.trim();
	const atlasDb = ATLAS_DB?.trim();
	const localUri = MONGODB_URI?.trim();
	const localDb = MONGODB_DB?.trim();

	// Prefer Atlas if populated; otherwise fall back to local MongoDB
	if (atlasUri) {
		return {
			uri: atlasUri,
			dbName: atlasDb || localDb || 'root-cause_db',
			target: 'Atlas'
		};
	}

	if (localUri) {
		return {
			uri: localUri,
			dbName: localDb || 'root-cause_db',
			target: 'Local'
		};
	}

	throw new Error(
		'Database configuration missing: Set either ATLAS_URI or MONGODB_URI in your .env file.'
	);
}

const { uri, dbName, target } = resolveDbConfig();

let client: MongoClient;
let clientPromise: Promise<MongoClient>;

declare global {
	// eslint-disable-next-line no-var
	var _mongoClientPromise: Promise<MongoClient> | undefined;
}

if (dev) {
	// Preserve connection across Vite HMR reloads in dev
	if (!globalThis._mongoClientPromise) {
		console.log(`[DB] Connecting to ${target} MongoDB (${dbName})...`);
		client = new MongoClient(uri);
		globalThis._mongoClientPromise = client.connect();
	}
	clientPromise = globalThis._mongoClientPromise;
} else {
	client = new MongoClient(uri);
	clientPromise = client.connect();
}

export async function getDb(): Promise<Db> {
	const connectedClient = await clientPromise;
	return connectedClient.db(dbName);
}