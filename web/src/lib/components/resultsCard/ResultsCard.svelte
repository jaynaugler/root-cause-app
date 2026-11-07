<script lang="ts">
    import type { Snippet } from 'svelte';
    import * as Card from '#lib/components/ui/card/index.js';
    import Button from '../ui/button/button.svelte';
    import ArrowRightIcon from '@lucide/svelte/icons/arrow-right';
    import buttonPlaceholder from '#lib/assets/buttonPlaceholderImg.png';

    let {
        title,
        description,
        href,
        children
    }: {
        title: string;
        description?: string;
        href: string;
        children?: Snippet;
    } = $props();
</script>

<Card.Root class="mx-auto w-full max-w-xs aspect-[1.1/1] bg-card-bg">
    <Card.Header class="-mt-(--card-spacing) px-0">
        <Card.Title class="w-full bg-card-title text-left text-slate-950 text-xl px-(--card-spacing) py-5 rounded-t-xl">
            {title}
        </Card.Title>

        {#if description}
            <Card.Description class="px-(--card-spacing) pt-3">
                {description}
            </Card.Description>
        {/if}
    </Card.Header>

    <Card.Content class="flex-1">
        {@render children?.()}
        <Button
            class="mt-auto self-end inline-flex h-12 w-48 items-center justify-between overflow-hidden bg-card-btn p-0 text-black hover:bg-[#4EAA27]"
            href={href}
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
    </Card.Content>
</Card.Root>