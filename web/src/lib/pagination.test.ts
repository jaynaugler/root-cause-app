import { describe, expect, it } from 'vitest';
import { MAX_ITEMS, pageItems } from './pagination.js';

describe('pageItems', () => {
	it('shows every page when there are few', () => {
		expect(pageItems(1, 1)).toEqual([1]);
		expect(pageItems(3, 6)).toEqual([1, 2, 3, 4, 5, 6]);
		expect(pageItems(7, 7)).toEqual([1, 2, 3, 4, 5, 6, 7]);
	});

	it('puts one gap after the start and one before the end', () => {
		expect(pageItems(1, 12)).toEqual([1, 2, 3, 4, 5, 'gap', 12]);
		expect(pageItems(4, 12)).toEqual([1, 2, 3, 4, 5, 'gap', 12]);
		expect(pageItems(6, 12)).toEqual([1, 'gap', 5, 6, 7, 'gap', 12]);
		expect(pageItems(9, 12)).toEqual([1, 'gap', 8, 9, 10, 11, 12]);
		expect(pageItems(12, 12)).toEqual([1, 'gap', 8, 9, 10, 11, 12]);
	});

	it('always shows the current, first and last page, in the same number of items', () => {
		for (let count = 8; count <= 30; count++) {
			for (let page = 1; page <= count; page++) {
				const items = pageItems(page, count);
				expect(items).toHaveLength(MAX_ITEMS);
				expect(items).toContain(page);
				expect(items[0]).toBe(1);
				expect(items.at(-1)).toBe(count);
			}
		}
	});
});
