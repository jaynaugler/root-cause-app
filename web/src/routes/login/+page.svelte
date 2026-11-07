<script lang="ts">
	import { goto } from '$app/navigation';
	import * as Card from '#lib/components/ui/card/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Label } from '#lib/components/ui/label/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import pattern from '#lib/assets/backgroundPattern.webp';

	let username = $state('');
	let password = $state('');
	let error = $state('');

	function handleSubmit(event: SubmitEvent) {
		event.preventDefault();

		if (!username.trim() || !password) {
			error = 'Enter your username and password.';
			return;
		}

		error = '';
		// TEMPORARY: there is no real login check yet.
		// The team will replace this with the real check later.
		goto('/submit');
	}
</script>

<svelte:head>
	<title>Organisation login · Our History Hub</title>
</svelte:head>

<main>
	<!-- Orange band with the pattern -->
	<section class="relative overflow-hidden bg-[#FF8C4B] px-4 pb-28 pt-8 text-center md:pb-32 md:pt-12">
		<!-- The pattern, covering the whole band, softened -->
		<div
			class="absolute inset-0 opacity-40 mix-blend-multiply"
			style="background-image: url({pattern}); background-size: auto 180px; background-repeat: repeat;"
		></div>

		<!-- NEW: patterned edge along the bottom of the band, like the hem of a cloth -->
	

		<!-- Heading and subtitle (sit on top of the pattern) -->
		<div class="relative">
			<h1 class="text-2xl font-extrabold tracking-wide text-[#2A1A10] sm:text-3xl md:text-5xl">
				SHARE YOUR RECORDS
			</h1>
			<p
				class="mt-4 inline-block rounded-lg bg-[#FFC49B] px-3 py-1.5 text-sm font-semibold text-[#2A1A10] md:px-4 md:py-2 md:text-base"
			>
				Log in to send a link to the Black Cultural Centre for review
			</p>
		</div>
	</section>

	<!-- The login card, overlapping the bottom of the band -->
	<div class="relative -mt-20 flex justify-center px-3 pb-16 sm:px-4 md:-mt-24">
		<Card.Root class="w-full max-w-md md:max-w-xl lg:max-w-2xl">
			<Card.Header>
				<Card.Title class="text-2xl">Organisation login</Card.Title>
				<Card.Description>Use the username and password given to your organisation.</Card.Description>
			</Card.Header>

			<Card.Content>
				<form onsubmit={handleSubmit} class="space-y-4" novalidate>
					<div class="space-y-2">
						<Label for="username">Username</Label>
						<Input id="username" name="username" autocomplete="username" bind:value={username} />
					</div>

					<div class="space-y-2">
						<Label for="password">Password</Label>
						<Input
							id="password"
							name="password"
							type="password"
							autocomplete="current-password"
							bind:value={password}
						/>
					</div>

					{#if error}
						<p class="text-sm font-medium text-[#A84A42]" role="alert">{error}</p>
					{/if}

					<div class="flex justify-center pt-2">
						<Button type="submit" class="bg-[#3F6B41] px-10 text-white hover:bg-[#335A35]">
							Log in
						</Button>
					</div>

					<p class="text-center text-sm text-muted-foreground">
						Need an account? Contact the Black Cultural Centre.
					</p>
				</form>
			</Card.Content>
		</Card.Root>
	</div>
</main>