<script lang="ts">
    import type { Snippet } from 'svelte';
    import * as Card from '#lib/components/ui/card/index.js';
    import type { SearchResult } from '#lib/search.js';
    import Button from '../ui/button/button.svelte';
    import ArrowRightIcon from '@lucide/svelte/icons/arrow-right';
    import buttonPlaceholder from '#lib/assets/buttonPlaceholderImg.png';

    let {
        result,
        number,
        anchorId,
        children
    }: {
        result: SearchResult;
        number: number;
        anchorId: string;
        children?: Snippet;
    } = $props();
</script>

<Card.Root id={anchorId} class="mx-auto w-full aspect-[1.1/1] bg-card-bg scroll-mt-6">
    <Card.Header class="-mt-(--card-spacing) px-0">
        <Card.Title class="w-full bg-card-title text-left text-slate-950 text-xl px-(--card-spacing) py-5 rounded-t-xl">
            {number}.
            {#if result.link}
                <a href={result.link} target="_blank" rel="noopener noreferrer" class="hover:underline">
                    {result.title ?? 'Untitled record'}
                </a>
            {:else}
                {result.title ?? 'Untitled record'}
            {/if}
        </Card.Title>

        {#if result.attribution}
            <Card.Description class="px-(--card-spacing) pt-3">
                {result.attribution}
            </Card.Description>
        {/if}
    </Card.Header>

    <Card.Content class="flex-1">
        {#if result.description}
            <p class="text-sm">{result.description}</p>
        {/if}

        {@render children?.()}

        {#if result.link}
            <Button
                class="mt-auto self-end inline-flex h-12 w-48 items-center justify-between overflow-hidden bg-card-btn p-0 text-black hover:bg-[#4EAA27]"
                href={result.link}
                target="_blank"
                rel="noopener noreferrer"
            >
                <img
                    src={buttonPlaceholder}
                    alt="Pattern on button"
                    class="size-12 shrink-0 rounded-l-md object-cover"
                />
                <span class="px-3">Go!</span>
                <ArrowRightIcon class="mx-3 size-5 shrink-0" aria-hidden="true" />
            </Button>
        {/if}
    </Card.Content>
</Card.Root>