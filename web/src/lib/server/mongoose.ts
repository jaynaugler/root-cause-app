// src/lib/server/mongoose.ts
// One shared Mongoose connection for every model (resources, users, ...).
// Mirrors db.ts: Atlas preferred, local fallback, globalThis singleton for dev HMR.
import mongoose from 'mongoose';
import { ATLAS_URI, ATLAS_DB, MONGODB_URI, MONGODB_DB } from '$app/env/private';
import { dev } from '$app/env';

function resolveDbConfig() {
	const atlasUri = ATLAS_URI?.trim();
	const atlasDb = ATLAS_DB?.trim();
	const localUri = MONGODB_URI?.trim();
	const localDb = MONGODB_DB?.trim();

	if (atlasUri) {
		return { uri: atlasUri, dbName: atlasDb || localDb || 'root-cause_db', target: 'Atlas' };
	}
	if (localUri) {
		return { uri: localUri, dbName: localDb || 'root-cause_db', target: 'Local' };
	}
	throw new Error(
		'Database configuration missing: Set either ATLAS_URI or MONGODB_URI in your .env file.'
	);
}

const { uri, dbName, target } = resolveDbConfig();

declare global {
	// eslint-disable-next-line no-var
	var _mongooseConnectionPromise: Promise<mongoose.Connection> | undefined;
}

function connect(): Promise<mongoose.Connection> {
	console.log(`[DB] Mongoose connecting to ${target} MongoDB (${dbName})...`);
	return mongoose.createConnection(uri, { dbName }).asPromise();
}

// In dev, reuse the connection stored on globalThis so Vite HMR reloads of this
// module don't open a new connection each time. Only connect if none exists yet.
const connectionPromise = dev
	? (globalThis._mongooseConnectionPromise ??= connect())
	: connect();

export function getConnection(): Promise<mongoose.Connection> {
	return connectionPromise;
}
