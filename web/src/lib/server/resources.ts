// src/lib/server/resources.ts
// The `resources` Mongoose model, on the shared connection from mongoose.ts.
import type mongoose from 'mongoose';
import { getConnection } from './mongoose.js';
import { resourceSchema, type ResourceDoc } from './resource-schema.js';

export async function getResourceModel(): Promise<mongoose.Model<ResourceDoc>> {
	const connection = await getConnection();
	// The connection survives Vite HMR reloads (globalThis singleton), so a
	// re-imported schema would fail with OverwriteModelError — reuse the
	// already-compiled model if present.
	return connection.models.Resource ?? connection.model<ResourceDoc>('Resource', resourceSchema);
}

export type { ResourceDoc } from './resource-schema.js';
