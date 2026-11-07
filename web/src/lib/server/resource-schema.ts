// src/lib/server/resource-schema.ts
// The Mongoose schema for the `resources` collection — deliberately free of
// SvelteKit env imports so scripts (tsx) can import it directly.
// Keep the enums in sync with api/app/ai.py (CATEGORIES) and
// web/src/scripts/setup-resources.ts (the optional DB-level validator).
import mongoose from 'mongoose';

export const RESOURCE_CATEGORIES = [
	'people',
	'places',
	'events',
	'organizations',
	'publications',
	'history'
] as const;

// 'unapproved' is unused today: everything is inserted 'approved' for now.
export const RESOURCE_STATUSES = ['pending', 'approved', 'unapproved'] as const;

// Shared length rules (enforced by the Mongoose schema, the DB validator, and
// the insert flow's description→summary fallback slice).
export const MAX_DESCRIPTION_LENGTH = 150;
export const MIN_SUMMARY_LENGTH = 250;

export type ResourceCategory = (typeof RESOURCE_CATEGORIES)[number];
export type ResourceStatus = (typeof RESOURCE_STATUSES)[number];

export interface ResourceDoc {
	title: string | null;
	link: string;
	description: string | null; // ≤150 chars, card teaser
	summary: string | null; // ≥250 chars, full cleaned summary (search data)
	attribution: string | null;
	resourceformat: string; // enum: ['pdf']
	contentcategory: ResourceCategory | null;
	imgurl: string | null;
	status: ResourceStatus;
	createdAt: Date;
}

// Unknown keys (details, raw from the fetch response) are an error, NOT
// silently dropped — strict: 'throw'. The insert flow must strip them itself.
export const resourceSchema = new mongoose.Schema<ResourceDoc>(
	{
		title: { type: String, default: null, maxlength: 300 },
		link: { type: String, required: true, match: /^https?:\/\//, maxlength: 2000 },
		description: { type: String, default: null, maxlength: MAX_DESCRIPTION_LENGTH },
		// minlength runs only on real strings — `null` (fallback records) stays legal.
		summary: { type: String, default: null, minlength: MIN_SUMMARY_LENGTH },
		attribution: { type: String, default: null },
		resourceformat: { type: String, required: true, enum: ['pdf'] },
		contentcategory: { type: String, enum: [...RESOURCE_CATEGORIES], default: null },
		imgurl: { type: String, default: null },
		status: { type: String, required: true, enum: [...RESOURCE_STATUSES] },
		createdAt: { type: Date, required: true }
	},
	{
		strict: 'throw',
		// No Mongoose version key: the DB-level $jsonSchema validator
		// (setup-resources.ts) rejects unknown properties like __v.
		versionKey: false
	}
);
