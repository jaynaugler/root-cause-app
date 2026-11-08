<script lang="ts">
	import ArrowUpIcon from '@lucide/svelte/icons/arrow-up';
	import { MAX_QUESTION_CHARS } from '#lib/search.js';

	// The question field with a round send button. Put it inside a <form>: Enter submits it.
	// - variant 'box':  big rounded box, grows with the text, Shift+Enter adds a new line,
	//                   the character count is always shown (new searches)
	// - variant 'pill': one slim line, the count only shows near the limit (follow-ups)
	let {
		value = $bindable(''),
		ref = $bindable(null),
		variant = 'box',
		name = 'question',
		placeholder = 'Ask anything about the archive…',
		label = 'Your question',
		disabled = false
	}: {
		value?: string;
		ref?: HTMLInputElement | HTMLTextAreaElement | null;
		variant?: 'box' | 'pill';
		name?: string;
		placeholder?: string;
		/** Read by screen readers instead of a visible label */
		label?: string;
		disabled?: boolean;
	} = $props();

	const left = $derived(MAX_QUESTION_CHARS - value.length);
	const nearLimit = $derived(left <= 50);

	// Box only: grow with the text instead of showing a scrollbar
	$effect(() => {
		value; // re-run on every change
		if (!(ref instanceof HTMLTextAreaElement)) return;
		ref.style.height = 'auto';
		ref.style.height = `${ref.scrollHeight}px`;
	});

	// Enter submits through the form, so use:enhance handles it like a button click
	function onkeydown(event: KeyboardEvent) {
		if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
			event.preventDefault();
			if (value.trim()) ref?.form?.requestSubmit();
		}
	}
</script>

{#snippet counter()}
	<span
		class="shrink-0 text-xs tabular-nums {nearLimit
			? 'font-medium text-red-500'
			: 'text-muted-foreground'}"
		aria-live="polite"
	>
		{value.length} / {MAX_QUESTION_CHARS}
	</span>
{/snippet}

{#snippet sendButton()}
	<button
		type="submit"
		disabled={disabled || !value.trim()}
		aria-label={variant === 'pill' ? 'Ask' : 'Search'}
		class="flex size-10 shrink-0 items-center justify-center rounded-full bg-search-btn text-white transition-colors hover:bg-search-btn-hover disabled:opacity-50"
	>
		<ArrowUpIcon class="size-5" />
	</button>
{/snippet}

{#if variant === 'pill'}
	<div
		class="flex items-center gap-3 rounded-full border bg-background py-1.5 pr-1.5 pl-5 shadow-md focus-within:ring-2 focus-within:ring-ring/40"
	>
		<input
			bind:this={ref}
			bind:value
			{name}
			{placeholder}
			{disabled}
			{onkeydown}
			maxlength={MAX_QUESTION_CHARS}
			aria-label={label}
			autocomplete="off"
			class="min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-muted-foreground disabled:opacity-60"
		/>
		{#if nearLimit}
			{@render counter()}
		{/if}
		{@render sendButton()}
	</div>
{:else}
	<div
		class="rounded-2xl border bg-background p-4 shadow-sm focus-within:ring-2 focus-within:ring-ring/40"
	>
		<textarea
			bind:this={ref}
			bind:value
			{name}
			{placeholder}
			{disabled}
			{onkeydown}
			rows="2"
			maxlength={MAX_QUESTION_CHARS}
			aria-label={label}
			class="block max-h-60 w-full resize-none bg-transparent text-base outline-none placeholder:text-muted-foreground disabled:opacity-60"
		></textarea>
		<div class="mt-3 flex items-center justify-end gap-3">
			{@render counter()}
			{@render sendButton()}
		</div>
	</div>
{/if}
