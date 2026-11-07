// src/lib/server/resources.ts
// Connection wiring for the `resources` Mongoose model. Mirrors db.ts:
// Atlas preferred, local fallback, globalThis singleton for dev HMR.
import mongoose from 'mongoose';
import { ATLAS_URI, ATLAS_DB, MONGODB_URI, MONGODB_DB } from '$app/env/private';
import { dev } from '$app/env';
import { resourceSchema, type ResourceDoc } from './resource-schema.js';

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

let connectionPromise = mongoose.createConnection(uri, { dbName }).asPromise();

if (dev) {
	// Preserve connection across Vite HMR reloads in dev (same pattern as db.ts)
	if (!globalThis._mongooseConnectionPromise) {
		console.log(`[DB] Mongoose connecting to ${target} MongoDB (${dbName})...`);
		globalThis._mongooseConnectionPromise = connectionPromise;
	}
	connectionPromise = globalThis._mongooseConnectionPromise;
}

export async function getResourceModel(): Promise<mongoose.Model<ResourceDoc>> {
	const connection = await connectionPromise;
	return connection.model<ResourceDoc>('Resource', resourceSchema);
}

export type { ResourceDoc } from './resource-schema.js';
