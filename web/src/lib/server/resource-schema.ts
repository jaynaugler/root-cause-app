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

// Formats the fetch pipeline produces (api/app/pdf.py, book.py, video.py).
export const RESOURCE_FORMATS = ['pdf', 'book', 'video'] as const;

// Shared length rules (enforced by the Mongoose schema, the DB validator, and
// the insert flow's description→summary fallback slice).
export const MAX_DESCRIPTION_LENGTH = 150;
export const MIN_SUMMARY_LENGTH = 250;

// A teaser mustn't end mid-word or mid-sentence: cut at the last sentence end
// within the cap, else the last whole word. Python mirrors this in
// api/scripts/populate_books.py (two languages, one rule — keep in sync).
export function truncateTeaser(text: string, cap: number = MAX_DESCRIPTION_LENGTH): string {
	if (text.length <= cap) return text;
	const cut = text.slice(0, cap);
	const sentenceEnd = Math.max(cut.lastIndexOf('. '), cut.lastIndexOf('! '), cut.lastIndexOf('? '));
	if (sentenceEnd >= cap * 0.5) return cut.slice(0, sentenceEnd + 1);
	const space = cut.lastIndexOf(' ');
	if (space > cap * 0.5) return cut.slice(0, space) + '…';
	return cut.slice(0, -1) + '…';
}

export type ResourceCategory = (typeof RESOURCE_CATEGORIES)[number];
export type ResourceStatus = (typeof RESOURCE_STATUSES)[number];

export interface ResourceDoc {
	title: string | null;
	link: string; // the resource itself (e.g. the direct PDF download)
	sitelink: string | null; // the page hosting it (e.g. bccns.com/resources/) — curator-supplied
	description: string | null; // ≤150 chars, card teaser
	summary: string | null; // ≥250 chars, full cleaned summary (search data)
	attribution: string | null;
	resourceformat: (typeof RESOURCE_FORMATS)[number]; // 'pdf' | 'book' | 'video'
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
		// Optional: the fetch pipeline can't derive it; the curator supplies it
		// at insert (falls back to null for direct PDFs from unknown sites).
		sitelink: { type: String, default: null, match: /^https?:\/\//, maxlength: 2000 },
		description: { type: String, default: null, maxlength: MAX_DESCRIPTION_LENGTH },
		// minlength runs only on real strings — `null` (fallback records) stays legal.
		summary: { type: String, default: null, minlength: MIN_SUMMARY_LENGTH },
		attribution: { type: String, default: null },
		resourceformat: { type: String, required: true, enum: [...RESOURCE_FORMATS] },
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
