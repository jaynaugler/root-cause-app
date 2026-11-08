// Checks what the browser sends before it goes on to search-api, so a bad request fails here
// with a clear message instead of as a 422 from search-api. The limits are the same as in
// search-server/search-api/main.py (Turn, SearchRequest, FacetsRequest).
// Used by the search action (routes/+page.server.ts, form fields) and the filter panels
// (routes/facets/[facet]/+server.ts, JSON).
import { z } from 'zod';
import {
	FACET_FIELDS,
	MAX_HISTORY,
	MAX_QUESTION_CHARS,
	MAX_SUMMARY_CHARS,
	type Filters,
	type HistoryTurn
} from '#lib/search.js';

export const questionSchema = z
	.string()
	.trim()
	.min(1, { message: 'Type a question.' })
	.max(MAX_QUESTION_CHARS, { message: `Question cannot exceed ${MAX_QUESTION_CHARS} characters.` });

export const searchSchema = z.object({ question: questionSchema });

// Earlier turns, sent with follow-ups and filter panels. Same limits as Turn in main.py.
const historySchema = z
	.array(
		z.object({
			question: z.string().trim().min(1).max(MAX_QUESTION_CHARS),
			summary: z
				.string()
				.nullable()
				.transform((s) => s?.slice(0, MAX_SUMMARY_CHARS) ?? null)
		})
	)
	.transform((turns) => turns.slice(-MAX_HISTORY));

// Missing or malformed history → no context (a plain new search), never an error.
// Takes the JSON text of a form field, or the already-parsed array of a JSON body.
export function parseHistory(raw: unknown): HistoryTurn[] {
	let value = raw;
	if (typeof raw === 'string') {
		if (!raw) return [];
		try {
			value = JSON.parse(raw);
		} catch {
			return [];
		}
	}
	const parsed = historySchema.safeParse(value);
	return parsed.success ? parsed.data : [];
}

// The checked values of one field. Same limits as SearchRequest.filters in main.py. Values are
// not trimmed: they must match the stored values exactly.
const filterValuesSchema = z.array(z.string().min(1).max(200)).max(20);

// Duplicates removed; null when the field has no valid values (it's then left out)
function cleanValues(values: unknown[]): string[] | null {
	const unique = [...new Set(values.filter((v) => typeof v === 'string'))];
	const parsed = filterValuesSchema.safeParse(unique);
	return parsed.success && parsed.data.length ? parsed.data : null;
}

// Checked values from a form, the normal HTML way for checkboxes: repeated fields,
// <input type="checkbox" name="contentcategory" value="people"> → contentcategory=people.
// Unknown fields are ignored (only FACET_FIELDS are read). A field with invalid values is
// dropped instead of failing the search, like a malformed history.
export function parseFilters(data: FormData): Filters {
	const filters: Filters = {};
	for (const field of FACET_FIELDS) {
		const values = cleanValues(data.getAll(field));
		if (values) filters[field] = values;
	}
	return filters;
}

// The same rules for a JSON object: { "contentcategory": ["people"] }
export function parseFiltersJson(raw: unknown): Filters {
	const filters: Filters = {};
	if (typeof raw !== 'object' || raw === null) return filters;
	for (const field of FACET_FIELDS) {
		const given = (raw as Record<string, unknown>)[field];
		const values = Array.isArray(given) ? cleanValues(given) : null;
		if (values) filters[field] = values;
	}
	return filters;
}

// The JSON body of POST /facets/[facet] (FacetOptionsRequest in #lib/search.ts). history and
// filters are checked leniently by the functions above, the rest strictly (a 400 if wrong):
// only our own panel code sends this, so a wrong value is a bug worth seeing.
export const facetsRequestSchema = z.object({
	question: questionSchema,
	// .default() first: in zod 4 a key with a transform is required otherwise
	history: z.unknown().default([]).transform(parseHistory),
	filters: z.unknown().default({}).transform(parseFiltersJson),
	search: z.string().max(100).default(''),
	sort: z.enum(['count', 'alpha']).default('count'),
	limit: z.number().int().min(1).max(100).default(8),
	cursor: z.string().max(200).nullish()
});
