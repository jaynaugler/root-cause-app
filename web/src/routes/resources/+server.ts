import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';
import { z } from 'zod';
import { getResourceModel } from '#lib/server/resources.js';
import { requireUserApi } from '#lib/server/guards.js';
import { RESOURCE_CATEGORIES } from '#lib/server/resource-schema.js';
import { MAX_DESCRIPTION_LENGTH, MIN_SUMMARY_LENGTH } from '#lib/server/resource-schema.js';
import {
	RESOURCE_CATEGORIES,
	RESOURCE_FORMATS,
	truncateTeaser,
	MAX_DESCRIPTION_LENGTH,
	MIN_SUMMARY_LENGTH
} from '#lib/server/resource-schema.js';

// Shape of the POST /api/pdf-metadata record, minus `details`/`raw` (UI-only,
// must not reach Mongo) and `status`/`createdAt` (stamped by this handler —
// a client never chooses its own approval status).
const insertSchema = z.object({
	title: z.string().nullish(),
	link: z.string(),
	sitelink: z.string().nullish(),
	description: z.string().nullish(),
	summary: z.string().nullish(),
	attribution: z.string().nullish(),
	resourceformat: z.enum(RESOURCE_FORMATS),
	contentcategory: z.enum(RESOURCE_CATEGORIES).nullish(),
	imgurl: z.string().nullish(),
	// Submissions (/submit) request pending review; a client claiming 'approved'
	// is rejected here, so approval stays a server-side decision. Omitted →
	// approved (the /pdf curator tool saves directly).
	status: z.literal('pending').optional()
});

// Schema invariants as insert-time rules (mirrors resource-schema.ts):
// - description ≤ MAX_DESCRIPTION_LENGTH (card teaser), null allowed
// - summary either null or ≥ MIN_SUMMARY_LENGTH
// A raw fallback record (no Gemini cleanup) arrives with its full OCR text in
// `description`: slice the teaser off and promote the rest to `summary` when
// it clears the minimum, so degraded records stay searchable.
function normalizeTexts(description: string | null, summary: string | null) {
	if (description !== null && description.length > MAX_DESCRIPTION_LENGTH) {
		const text = description;
		return { description: truncateTeaser(text), summary: text.length >= MIN_SUMMARY_LENGTH ? text : null };
	}
	if (summary !== null && summary.length < MIN_SUMMARY_LENGTH) return { description, summary: null };
	return { description, summary };
}

export const POST: RequestHandler = async (event) => {
	// First line, before reading anything: not logged in → 401, nothing below runs.
	requireUserApi(event);
	const { request } = event;

	const parse = insertSchema.safeParse(await request.json().catch(() => null));
	if (!parse.success) {
		return json({ error: 'Invalid resource record.', issues: parse.error.issues }, { status: 400 });
	}
	const data = parse.data;

	const { description, summary } = normalizeTexts(data.description ?? null, data.summary ?? null);

	try {
		const Resource = await getResourceModel();
		const resource = await Resource.create({
			title: data.title ?? null,
			link: data.link,
			sitelink: data.sitelink ?? null,
			description,
			summary,
			attribution: data.attribution ?? null,
			resourceformat: data.resourceformat,
			contentcategory: data.contentcategory ?? null,
			imgurl: data.imgurl ?? null,
			// Curator saves default to approved; /submit requests pending review.
			status: data.status === 'pending' ? 'pending' : 'approved',
			createdAt: new Date()
		});
		return json(String(resource._id), { status: 201 });
	} catch (error) {
		// Mongoose validation errors (bad enum, bad link, …) are client data problems.
		const issues =
			error instanceof Error && error.name === 'ValidationError'
				? Object.values((error as { errors?: Record<string, { message?: string }> }).errors ?? {}).map(
						(e) => e.message ?? 'validation failed'
					)
				: null;
		if (issues) return json({ error: 'Resource failed validation.', issues }, { status: 400 });
		console.error('Insert failed:', error);
		return json({ error: 'Could not reach the database.' }, { status: 502 });
	}
};
