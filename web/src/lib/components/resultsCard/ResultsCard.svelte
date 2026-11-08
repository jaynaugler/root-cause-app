<script lang="ts">
    import type { Snippet } from 'svelte';
    import * as Card from '#lib/components/ui/card/index.js';
    import type { SearchResult } from '#lib/search.js';
    import Button from '../ui/button/button.svelte';
    import ArrowRightIcon from '@lucide/svelte/icons/arrow-right';
    import GreenPattern from '#lib/assets/GreenPattern.jpg';
    // Icons for different link types
    import Youtube from '@lucide/svelte/icons/video';
    import FileText from '@lucide/svelte/icons/file-text';
    import Headphones from '@lucide/svelte/icons/headphones';
    import BookOpen from '@lucide/svelte/icons/book-open';
    import LinkIcon from '@lucide/svelte/icons/link';

    let {
        result,
        number,
        anchorId,
        children,
        searchMode = false
    }: {
        result: SearchResult;
        number: number;
        anchorId: string;
        children?: Snippet;
        searchMode?: boolean;
    } = $props();

    // Prefer the human-readable hosting page; fall back to the resource itself.
    let href = $derived(result.sitelink || result.link);

    type LinkType = 'youtube' | 'pdf' | 'podcast' | 'book' | 'uncategorized';

    function classifyLink(result: SearchResult, href: string | undefined): LinkType {
        if (!href) return 'uncategorized';

        let url: URL | undefined;

        try {
            url = new URL(href);
        } catch {
            // The link may not be an absolute URL.
        }

        const hostname = url?.hostname.toLowerCase() ?? '';
        const pathname = (url?.pathname ?? href.split(/[?#]/)[0]).toLowerCase();
        const format = (result.resourceformat ?? '').toLowerCase();

        if (hostname === 'youtu.be' || hostname.endsWith('.youtube.com') || hostname === 'youtube.com') {
            return 'youtube';
        }

        if (pathname.endsWith('.pdf')) {
            return 'pdf';
        }

        if (format.includes('podcast') || format.includes('audio')) {
            return 'podcast';
        }

        if (format.includes('book') || format.includes('monograph')) {
            return 'book';
        }

        return 'uncategorized';
    }

    let linkType = $derived(classifyLink(result, href));
</script>

<Card.Root id={anchorId} class="mx-auto w-full bg-card-bg scroll-mt-6 {searchMode ? '' : 'aspect-[1.1/1]'}">
    <Card.Header class="-mt-(--card-spacing) px-0">
        <Card.Title class="flex w-full items-start gap-2 bg-card-title text-left text-white text-xl px-(--card-spacing) py-5 rounded-t-xl">
            <span class="shrink-0">{number}.</span>
            {#if href}
                <a
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    class="min-w-0 flex-1 {searchMode ? '' : 'line-clamp-2'} hover:underline"
                    title={result.title ?? 'Untitled record'}
                >
                    {result.title ?? 'Untitled record'}
                </a>
            {:else}
                <span class="min-w-0 flex-1 {searchMode ? '' : 'line-clamp-2'}" title={result.title ?? 'Untitled record'}>
                    {result.title ?? 'Untitled record'}
                </span>
            {/if}
        </Card.Title>

        {#if result.attribution}
            <Card.Description class="px-(--card-spacing) pt-3">
                {result.attribution}
            </Card.Description>
        {/if}
    </Card.Header>

    <Card.Content class="flex-1">
        {#if searchMode}
            <div class="flex items-start justify-between gap-4">
                <div class="min-w-0">
                    {#if result.description}
                        <p class="text-sm">{result.description}</p>
                    {/if}
                </div>
            </div>
        {:else if result.description}
            <p class="text-sm">{result.description}</p>
        {/if}

        {#if searchMode && result.summary}
            <details class="rounded-lg border border-border/60 bg-background/50 p-3">
                <summary class="cursor-pointer text-sm font-medium select-none">Stored summary</summary>
                <p class="mt-3 text-sm leading-relaxed whitespace-pre-wrap">{result.summary}</p>
            </details>
        {/if}

        {@render children?.()}

        {#if href}
            <Button
                class="relative mt-auto self-end inline-flex h-10 w-38 overflow-hidden bg-card-btn p-0 text-white hover:bg-card-btn-hover"
                href={href}
                target="_blank"
                rel="noopener noreferrer"
            >
                <img
                    src={GreenPattern}
                    alt=""
                    class="absolute left-0 top-0 size-10 shrink-0 rounded-l-md object-cover"
                />

                <span class="absolute inset-y-0 left-10 right-0 flex items-center justify-center gap-2 whitespace-nowrap">
                    {#if linkType === 'youtube'}
                        <Youtube class="size-5 shrink-0" aria-hidden="true" />
                        Video
                    {:else if linkType === 'pdf'}
                        <FileText class="size-5 shrink-0" aria-hidden="true" />
                        PDF
                    {:else if linkType === 'podcast'}
                        <Headphones class="size-5 shrink-0" aria-hidden="true" />
                        Podcast
                    {:else if linkType === 'book'}
                        <BookOpen class="size-5 shrink-0" aria-hidden="true" />
                        Book
                    {:else}
                        <LinkIcon class="size-5 shrink-0" aria-hidden="true" />
                        Link
                    {/if}
                </span>
            </Button>
        {/if} 
    </Card.Content>
</Card.Root>