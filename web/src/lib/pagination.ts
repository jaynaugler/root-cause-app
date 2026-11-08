// Which page numbers the page bar shows (components/search/Pagination.svelte).
// Up to 7 pages: all of them. More: the first, the last, the current one with its neighbours,
// and a gap ('gap', drawn as "…") for each run that is left out. Always 7 items, so the bar
// doesn't change width while you click through:
//   page 1 of 12 → 1 2 3 4 5 … 12
//   page 6 of 12 → 1 … 5 6 7 … 12
//   page 12      → 1 … 8 9 10 11 12
export type PageItem = number | 'gap';

export const MAX_ITEMS = 7;

export function pageItems(page: number, pageCount: number): PageItem[] {
	const range = (from: number, to: number) =>
		Array.from({ length: to - from + 1 }, (_, i) => from + i);

	if (pageCount <= MAX_ITEMS) return range(1, pageCount);
	// Near the start or the end: one gap only, five numbers on that side
	if (page <= 4) return [...range(1, 5), 'gap', pageCount];
	if (page >= pageCount - 3) return [1, 'gap', ...range(pageCount - 4, pageCount)];
	return [1, 'gap', page - 1, page, page + 1, 'gap', pageCount];
}
