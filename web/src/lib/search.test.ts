// Tests for the filter helpers in search.ts. Plain functions: no database, no server.
import { describe, expect, it } from 'vitest';
import { activeFacetCount, fold, highlightParts, pillLabel, valueLabel } from './search.js';

describe('valueLabel', () => {
	it('makes stored values readable', () => {
		expect(valueLabel('contentcategory', 'people')).toBe('People');
		expect(valueLabel('resourceformat', 'pdf')).toBe('PDF');
		expect(valueLabel('resourceformat', 'book')).toBe('Books');
		expect(valueLabel('resourceformat', 'video')).toBe('Videos');
		expect(valueLabel('resourceformat', 'podcast')).toBe('Podcasts');
		// A format without a label yet: capitalized
		expect(valueLabel('resourceformat', 'map')).toBe('Map');
	});

	it('shows source names as stored', () => {
		expect(valueLabel('attribution', 'black cultural centre')).toBe('black cultural centre');
	});
});

describe('pillLabel', () => {
	it('is the field name alone when nothing is checked', () => {
		expect(pillLabel('contentcategory', [])).toEqual({ full: 'Category', names: '', more: 0 });
	});

	it('adds the checked value', () => {
		expect(pillLabel('resourceformat', ['pdf'])).toEqual({
			full: 'Format: PDF',
			names: 'PDF',
			more: 0
		});
	});

	it('lists several values in the order they were checked while they are short', () => {
		// "People, Publications" = 20 characters, under 28
		expect(pillLabel('contentcategory', ['people', 'publications']).names).toBe(
			'People, Publications'
		);
		expect(pillLabel('resourceformat', ['book', 'pdf']).names).toBe('Books, PDF');
	});

	it('shows the first value and +N when the list gets too long', () => {
		const label = pillLabel('attribution', [
			'Black Cultural Centre for Nova Scotia',
			'Nova Scotia Archives'
		]);
		expect(label.names).toBe('Black Cultural Centre for Nova Scotia');
		expect(label.more).toBe(1);
		// The tooltip / screen-reader text keeps every name
		expect(label.full).toBe(
			'Source: Black Cultural Centre for Nova Scotia, Nova Scotia Archives'
		);
	});

	it('keeps one long name whole: the pill cuts it with an ellipsis, not +N', () => {
		const label = pillLabel('attribution', ['Black Cultural Centre for Nova Scotia']);
		expect(label).toMatchObject({ names: 'Black Cultural Centre for Nova Scotia', more: 0 });
	});
});

describe('activeFacetCount', () => {
	it('counts fields with a filter, not checked values', () => {
		expect(activeFacetCount({})).toBe(0);
		expect(activeFacetCount({ contentcategory: ['people', 'history'] })).toBe(1);
		expect(activeFacetCount({ contentcategory: ['people'], attribution: ['BCCNS'] })).toBe(2);
	});

	it('ignores empty lists', () => {
		expect(activeFacetCount({ contentcategory: [] })).toBe(0);
	});
});

describe('fold', () => {
	it('removes case and accents, like fold() in search-api', () => {
		expect(fold('Université Sainte-Anne')).toBe('universite sainte-anne');
		expect(fold('ÉCOLE')).toBe('ecole');
	});
});

describe('highlightParts', () => {
	it('marks the matching letters, ignoring case and accents', () => {
		expect(highlightParts('Université Sainte-Anne', 'UNIV')).toEqual([
			{ text: 'Univ', match: true },
			{ text: 'ersité Sainte-Anne', match: false }
		]);
	});

	it('maps a match on an unaccented search back to the accented letters', () => {
		expect(highlightParts('Université', 'site')).toEqual([
			{ text: 'Univer', match: false },
			{ text: 'sité', match: true }
		]);
	});

	it('marks every match', () => {
		expect(highlightParts('Nova Scotia, Nova', 'nova')).toEqual([
			{ text: 'Nova', match: true },
			{ text: ' Scotia, ', match: false },
			{ text: 'Nova', match: true }
		]);
	});

	it('returns the whole label when nothing matches or nothing was typed', () => {
		expect(highlightParts('Dalhousie', 'xyz')).toEqual([{ text: 'Dalhousie', match: false }]);
		expect(highlightParts('Dalhousie', '  ')).toEqual([{ text: 'Dalhousie', match: false }]);
	});
});
