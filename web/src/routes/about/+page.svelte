<script lang="ts">
	import * as Card from '#lib/components/ui/card/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import pattern from '#lib/assets/backgroundPattern.webp';
</script>

<svelte:head>
	<title>About · Our History Hub</title>
</svelte:head>

<main>
	<!-- Orange band with the pattern (same as the submit page) -->
	<section class="relative overflow-hidden bg-[#FF8C4B] px-4 pb-28 pt-8 text-center md:pb-32 md:pt-12">
		<div
			class="absolute inset-0 opacity-40 mix-blend-multiply"
			style="background-image: url({pattern}); background-size: auto 180px; background-repeat: repeat;"
		></div>

		<div class="relative">
			<h1 class="text-2xl font-extrabold tracking-wide text-[#2A1A10] sm:text-3xl md:text-5xl">
				ABOUT OUR HISTORY HUB
			</h1>
			<p
				class="mt-4 inline-block rounded-lg bg-[#FFC49B] px-3 py-1.5 text-sm font-semibold text-[#2A1A10] md:px-4 md:py-2 md:text-base"
			>
				The Black Cultural Centre for Nova Scotia's search hub for records of Black history.
			</p>
		</div>
	</section>

	<!-- What it is + image placeholder -->
	<section class="mx-auto max-w-6xl px-4 pt-16 pb-4 md:pt-20">
		<div class="grid items-center gap-8 md:grid-cols-2">
			<div class="space-y-4">
				<h2 class="text-xl font-bold text-[#2A1A10] md:text-2xl">One search, all the records</h2>
				<p class="text-[#2A1A10]">
					Our History Hub gathers records of Black history in Nova Scotia — documents, books and
					videos held by archives, libraries and community members — and makes them searchable
					from one place. Instead of hunting through separate collections, you type a question
					and the hub finds the records that answer it.
				</p>
			</div>

			<!-- IMAGE PLACEHOLDER 1: e.g. a screenshot of a search + its answer -->
			<figure class="rounded-2xl border-2 border-dashed border-[#D2CBBD] bg-[#F7F5ED] p-4">
				<div
					class="flex aspect-[4/3] items-center justify-center rounded-xl bg-[#FFC49B]/40 p-4 text-center text-sm font-medium text-[#6B6458]"
				>
					Image placeholder — e.g. a screenshot of the search page with a question and answer
				</div>
			</figure>
		</div>
	</section>

	<!-- How it works: three cards -->
	<section class="mx-auto max-w-6xl px-4 py-12">
		<h2 class="text-xl font-bold text-[#2A1A10] md:text-2xl">How it works</h2>
		<div class="mt-6 grid gap-4 md:grid-cols-3">
			<Card.Root class="bg-card-bg">
				<Card.Header>
					<Card.Title class="text-lg">Ask, don't hunt</Card.Title>
					<Card.Description>
						Type a question in plain words. The hub searches records by meaning, not just
						keywords, and writes a short summary of what they say — with each claim linked to
						the record it came from.
					</Card.Description>
				</Card.Header>
			</Card.Root>

			<Card.Root class="bg-card-bg">
				<Card.Header>
					<Card.Title class="text-lg">Filter while you dig</Card.Title>
					<Card.Description>
						Narrow results by category, source and format. The counts next to each filter show
						how many records match, so you always know what you've found.
					</Card.Description>
				</Card.Header>
			</Card.Root>

			<Card.Root class="bg-card-bg">
				<Card.Header>
					<Card.Title class="text-lg">Browse the newest</Card.Title>
					<Card.Description>
						Not looking for anything in particular? Start from the most recently added records
						and work your way through the collection.
					</Card.Description>
				</Card.Header>
			</Card.Root>
		</div>
	</section>

	<!-- Community / contribute + image placeholder -->
	<section class="mx-auto max-w-6xl px-4 pb-16">
		<div class="grid items-center gap-8 md:grid-cols-2">
			<!-- IMAGE PLACEHOLDER 2: e.g. an archive photo, the Centre, or volunteers at work -->
			<figure class="rounded-2xl border-2 border-dashed border-[#D2CBBD] bg-[#F7F5ED] p-4 md:order-last">
				<div
					class="flex aspect-[4/3] items-center justify-center rounded-xl bg-[#FFC49B]/40 p-4 text-center text-sm font-medium text-[#6B6458]"
				>
					Image placeholder — e.g. an archive photo or the Black Cultural Centre
				</div>
			</figure>

			<div class="space-y-4">
				<h2 class="text-xl font-bold text-[#2A1A10] md:text-2xl">Built with the community</h2>
				<p class="text-[#2A1A10]">
					The records you can find here were contributed by people and institutions who
					care about Black history in Nova Scotia. If you know of a record — a PDF, an
					ebook, a video with a transcript — you can send it in as a request.
				</p>
				<p class="text-[#2A1A10]">
					Every submission is reviewed by the Black Cultural Centre before it appears in
					search, so the records stay trustworthy.
				</p>
			</div>
		</div>
	</section>

	<!-- Call to action -->
	<section class="border-t border-orange-100 bg-[#F6E2D1] px-4 py-12 text-center">
		<h2 class="text-xl font-bold tracking-wide text-[#2A1A10] sm:text-2xl">READY TO EXPLORE?</h2>
		<p class="mx-auto mt-3 max-w-xl text-[#2A1A10]">
			Ask your first question, or browse the most recent records.
		</p>
		<Button
			href="/"
			class="mt-6 bg-[#3F6B41] px-10 text-white hover:bg-[#335A35]"
		>
			Start searching
		</Button>
	</section>
</main>
