<script lang="ts">
	import { applyAction, enhance, type SubmitFunction } from '$app/forms';
	import { onMount, tick } from 'svelte';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import SearchSummary from '#lib/components/search/SearchSummary.svelte';
	import ResultsCard from '#lib/components/resultsCard/ResultsCard.svelte';
	import MagicBorder from '#lib/components/search/MagicBorder.svelte';
	import { MAX_HISTORY, type ThreadTurn } from '#lib/search.js';

	let { form } = $props();

	type Mode = 'new' | 'followup';

	// sessionStorage: survives a refresh, cleared when the tab closes, separate per tab
	const STORAGE_KEY = 'search-thread';
	const MAX_THREAD = 10; // keep only the newest turns so storage can't grow forever

	// The conversation: one entry per answered question
	let thread = $state<ThreadTurn[]>([]);
	// false until the saved thread is loaded, so the save effect can't overwrite it with []
	let restored = $state(false);

	// Load the saved thread. onMount runs only in the browser (the server has no sessionStorage).
	onMount(() => {
		try {
			const saved = JSON.parse(sessionStorage.getItem(STORAGE_KEY) ?? '[]');
			// Ignore anything that doesn't look like a thread (e.g. saved by an older version)
			if (
				Array.isArray(saved) &&
				saved.every((t) => typeof t?.question === 'string' && Array.isArray(t?.results))
			) {
				thread = saved.slice(-MAX_THREAD);
			}
		} catch {
			// Storage blocked (private mode) or corrupt JSON: start empty, like before
		}
		restored = true;
	});

	// Save whenever the thread changes
	$effect(() => {
		if (!restored) return;
		try {
			if (thread.length) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(thread));
			else sessionStorage.removeItem(STORAGE_KEY);
		} catch {
			// Storage full or blocked: the page still works, it just won't survive a refresh
		}
	});
	// Set while a request is running: which form sent it, and the question (shown as a placeholder turn)
	let pending = $state<{ mode: Mode; question: string } | null>(null);
	// Which form the last error belongs to, so it shows under the right input
	let errorFor = $state<Mode>('new');
	let followUp = $state('');
	let followUpInput = $state<HTMLInputElement | null>(null);

	// Without JavaScript the form does a normal page reload and the answer arrives as `form`
	const turns = $derived<ThreadTurn[]>(
		thread.length ? thread : form?.results ? [form as unknown as ThreadTurn] : []
	);
	// While a NEW search runs, hide the old thread — it is about to be replaced
	const visibleTurns = $derived(pending?.mode === 'new' ? [] : turns);

	// Chat-style spacing: the newest follow-up (or its loading placeholder) is at least one screen
	// tall, so it can always be scrolled to the top even when its answer is short. Not for the
	// first search, which already sits right under the header.
	const FILL_SCREEN = 'min-h-[calc(100dvh-8rem)]'; // minus the sticky follow-up bar
	const padLatestTurn = $derived(visibleTurns.length > 1 && !pending);

	// Sent with each follow-up: the last turns' questions and summaries (records are not needed)
	const historyJson = $derived(
		JSON.stringify(
			turns.slice(-MAX_HISTORY).map(({ question, summary }) => ({ question, summary }))
		)
	);

	// One submit handler for both forms; `mode` decides whether the answer replaces or extends the thread
	// Scroll an element to the top of the screen (scroll-mt-6 on the target leaves a small gap)
	function scrollToTop(id: string) {
		document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
	}

	function submitTo(mode: Mode): SubmitFunction {
		return ({ formData }) => {
			pending = { mode, question: formData.get('question')?.toString().trim() ?? '' };
			errorFor = mode;

			// Follow-up: move the question + loading placeholder to the top right away, so the
			// answer appears where you are looking (not off-screen below the follow-up bar).
			// Not awaited: the request starts immediately.
			if (mode === 'followup') tick().then(() => scrollToTop('turn-pending'));

			return async ({ result }) => {
				pending = null;

				if (result.type === 'success' && result.data?.results) {
					const turn = result.data as unknown as ThreadTurn;
					thread = mode === 'new' ? [turn] : [...thread, turn].slice(-MAX_THREAD);
					if (mode === 'followup') followUp = '';
					form = null; // clear any old error message

					// The answer replaces the placeholder at the same spot; re-align in case the
					// user scrolled while waiting, then put the cursor back for the next question
					await tick();
					if (mode === 'followup') scrollToTop(`turn-${thread.length - 1}`);
					followUpInput?.focus({ preventScroll: true });
				} else {
					// Validation error or API failure: puts it in `form` so the messages below render
					await applyAction(result);
				}
			};
		};
	}
</script>

{#snippet errors(mode: Mode)}
	{#if errorFor === mode && form?.errors?.question}
		<p class="text-sm font-medium text-red-500">{form.errors.question[0]}</p>
	{/if}
	{#if errorFor === mode && form?.message}
		<p class="text-sm font-medium text-red-500">{form.message}</p>
	{/if}
{/snippet}

<main class="container mx-auto max-w-6xl px-4 pt-12 space-y-8">
	<header class="space-y-4">
		<h1 class="text-2xl font-semibold">Search the archive</h1>

		<!-- New search: starts a fresh thread -->
		<form method="POST" action="?/search" class="w-full space-y-2" use:enhance={submitTo('new')}>
			<div class="flex gap-2">
				<MagicBorder active={pending?.mode === 'new'} class="flex-1">
					<Input
						name="question"
						placeholder="Ask a question, e.g. Who was Viola Desmond?"
						value={form?.question ?? ''}
						disabled={!!pending}
					/>
				</MagicBorder>
				<Button type="submit" disabled={!!pending}>
					{pending?.mode === 'new' ? 'Searching…' : 'Search'}
				</Button>
			</div>
			{@render errors('new')}
		</form>
	</header>

	<!-- The thread: question → summary → records, oldest first -->
	{#each visibleTurns as turn, t (t)}
		{@const isLatest = t === visibleTurns.length - 1}
		<article
			id="turn-{t}"
			class="scroll-mt-6 space-y-4 {isLatest && padLatestTurn ? FILL_SCREEN : ''}"
		> 
			<h2 class="text-lg font-medium">{turn.question}</h2>

			<SearchSummary summary={turn.summary} provider={turn.provider} anchorPrefix="t{t}-result-" />

			<!-- Records: open for the newest turn, collapsed for older ones -->
			<details open={isLatest} class="group space-y-3">
				<summary class="cursor-pointer text-sm font-medium text-muted-foreground select-none">
					{turn.results.length} record{turn.results.length === 1 ? '' : 's'} found
				</summary>
				<div class="mt-3 grid grid-cols-1 gap-3 md:grid-cols-3">
					{#each turn.results as result, i (result.id)}
						<ResultsCard {result} number={i + 1} anchorId="t{t}-result-{i + 1}" />
					{/each}
				</div>
			</details>
		</article>
	{/each}

	<!-- Placeholder while waiting (Ollama can take several seconds) -->
	{#if pending}
		<article
			id="turn-pending"
			class="scroll-mt-6 space-y-4 {pending.mode === 'followup' ? FILL_SCREEN : ''}"
			aria-live="polite"
		>
			<h2 class="text-lg font-medium">{pending.question}</h2>
			<div class="space-y-2 rounded-xl border p-6">
				<div class="h-4 w-3/4 animate-pulse rounded bg-muted"></div>
				<div class="h-4 w-full animate-pulse rounded bg-muted"></div>
				<div class="h-4 w-2/3 animate-pulse rounded bg-muted"></div>
				<p class="pt-2 text-sm text-muted-foreground">Searching the records and writing a summary…</p>
			</div>
		</article>
	{/if}

	<!-- Follow-up: only once there is something to follow up on. Sticky so it stays in reach. -->
	{#if turns.length > 0}
		<!-- Fades the content out above the bar so it reads as "pinned", not as more page -->
		<form
			method="POST"
			action="?/search"
			class="sticky bottom-0 bg-linear-to-t from-background from-80% to-transparent pt-6 pb-4"
			use:enhance={submitTo('followup')}
		>
			<input type="hidden" name="history" value={historyJson} />
			<!-- Light tinted panel so it doesn't read as another result card (temporary styling) -->
			<div class="space-y-2 rounded-xl border bg-muted p-3 shadow-lg">
				<label for="follow-up" class="block px-1 text-xs font-medium text-muted-foreground">
					Follow-up question — uses the answers above as context
				</label>
				<div class="flex gap-2">
					<MagicBorder active={pending?.mode === 'followup'} class="flex-1">
						<Input
							id="follow-up"
							name="question"
							placeholder="Ask a follow-up…"
							bind:value={followUp}
							bind:ref={followUpInput}
							disabled={!!pending}
						/>
					</MagicBorder>
					<Button type="submit" disabled={!!pending}>
						{pending?.mode === 'followup' ? 'Asking…' : 'Ask'}
					</Button>
				</div>
				{@render errors('followup')}
			</div>
		</form>
	{:else}
		<div class="pb-12"></div>
	{/if}
</main>
