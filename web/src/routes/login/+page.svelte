<script lang="ts">
	import { enhance } from '$app/forms';
	import * as Card from '#lib/components/ui/card/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Label } from '#lib/components/ui/label/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import pattern from '#lib/assets/backgroundPattern.webp';
	import type { PageProps } from './$types';

	// `form` = what the action in +page.server.ts returned after a failed login
	// (field errors, or the general "Invalid email or password." message).
	let { form }: PageProps = $props();
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
				<Card.Description>Log in with your email and password.</Card.Description>
			</Card.Header>

			<Card.Content>
				<!-- Posts to the default action in +page.server.ts. novalidate: the server
				     does the checking and shows its messages below each field. -->
				<form method="POST" use:enhance class="space-y-4" novalidate>
					<div class="space-y-2">
						<Label for="email">Email</Label>
						<Input
							id="email"
							name="email"
							type="email"
							autocomplete="email"
							value={form?.email ?? ''}
						/>
						{#if form?.errors?.email}
							<p class="text-sm font-medium text-[#A84A42]">{form.errors.email[0]}</p>
						{/if}
					</div>

					<div class="space-y-2">
						<Label for="password">Password</Label>
						<Input id="password" name="password" type="password" autocomplete="current-password" />
						{#if form?.errors?.password}
							<p class="text-sm font-medium text-[#A84A42]">{form.errors.password[0]}</p>
						{/if}
					</div>

					{#if form?.message}
						<p class="text-sm font-medium text-[#A84A42]" role="alert">{form.message}</p>
					{/if}

					<div class="flex justify-center pt-2">
						<Button type="submit" class="bg-[#3F6B41] px-10 text-white hover:bg-[#335A35]">
							Log in
						</Button>
					</div>

					<p class="text-center text-sm text-muted-foreground">
						Need an account? <a href="/register" class="underline">Create one</a>
					</p>
				</form>
			</Card.Content>
		</Card.Root>
	</div>
</main>