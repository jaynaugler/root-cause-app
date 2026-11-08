// Tests for search-params.ts: what the search action and the filter panels accept.
import { describe, expect, it } from 'vitest';
import {
	browseRequestSchema,
	facetsRequestSchema,
	parseFilters,
	parseFiltersJson,
	parseHistory
} from './search-params.js';

describe('parseFiltersJson', () => {
	it('keeps known fields, drops duplicates', () => {
		expect(
			parseFiltersJson({ contentcategory: ['people', 'people', 'history'], attribution: ['BCCNS'] })
		).toEqual({ contentcategory: ['people', 'history'], attribution: ['BCCNS'] });
	});

	it('ignores unknown fields, empty lists and non-strings', () => {
		expect(
			parseFiltersJson({ year: ['1946'], contentcategory: [], resourceformat: [42, 'pdf'] })
		).toEqual({ resourceformat: ['pdf'] });
	});

	it('drops a field with too many values instead of failing', () => {
		const tooMany = Array.from({ length: 21 }, (_, i) => `v${i}`);
		expect(parseFiltersJson({ attribution: tooMany })).toEqual({});
	});

	it('returns no filters for anything that is not an object', () => {
		expect(parseFiltersJson(null)).toEqual({});
		expect(parseFiltersJson('people')).toEqual({});
	});
});

describe('parseFilters (form fields)', () => {
	it('reads repeated checkbox fields', () => {
		const data = new FormData();
		data.append('contentcategory', 'people');
		data.append('contentcategory', 'history');
		data.append('question', 'not a filter');
		expect(parseFilters(data)).toEqual({ contentcategory: ['people', 'history'] });
	});
});

describe('parseHistory', () => {
	const turn = { question: 'Who was Viola Desmond?', summary: 'A businesswoman [1].' };

	it('accepts the JSON text of a form field and an already-parsed array', () => {
		expect(parseHistory(JSON.stringify([turn]))).toEqual([turn]);
		expect(parseHistory([turn])).toEqual([turn]);
	});

	it('keeps only the last 3 turns', () => {
		const turns = [1, 2, 3, 4].map((n) => ({ question: `Q${n}`, summary: null }));
		expect(parseHistory(turns).map((t) => t.question)).toEqual(['Q2', 'Q3', 'Q4']);
	});

	it('turns anything malformed into no history', () => {
		expect(parseHistory('not json')).toEqual([]);
		expect(parseHistory([{ summary: 'no question' }])).toEqual([]);
		expect(parseHistory(undefined)).toEqual([]);
	});
});

describe('facetsRequestSchema', () => {
	it('fills in the defaults', () => {
		expect(facetsRequestSchema.parse({ question: '  Viola  ' })).toEqual({
			question: 'Viola',
			history: [],
			filters: {},
			search: '',
			sort: 'count',
			limit: 8
		});
	});

	it('rejects a wrong sort or limit, or a too long question', () => {
		expect(facetsRequestSchema.safeParse({ question: 'x', sort: 'random' }).success).toBe(false);
		expect(facetsRequestSchema.safeParse({ question: 'x', limit: 500 }).success).toBe(false);
		expect(facetsRequestSchema.safeParse({ question: 'x'.repeat(501) }).success).toBe(false);
	});

	it('allows no question: browsing, before the first question', () => {
		expect(facetsRequestSchema.parse({}).question).toBe('');
		expect(facetsRequestSchema.parse({ question: '   ' }).question).toBe('');
	});
});

describe('browseRequestSchema', () => {
	it('reads the filters with the same rules, and allows none', () => {
		expect(browseRequestSchema.parse({ filters: { contentcategory: ['people'], year: ['1946'] } })).toEqual(
			{ filters: { contentcategory: ['people'] } }
		);
		expect(browseRequestSchema.parse({})).toEqual({ filters: {} });
	});
});
