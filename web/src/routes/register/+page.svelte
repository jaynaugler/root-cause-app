<script lang="ts">
	import { enhance } from '$app/forms';
	import * as Card from '#lib/components/ui/card/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Label } from '#lib/components/ui/label/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import pattern from '#lib/assets/backgroundPattern.webp';
	import type { PageProps } from './$types';

	// `form` = whatever the action returned: fail(400, {...}) data, or undefined.
	let { form }: PageProps = $props();
</script>

<svelte:head>
	<title>Create account · Our History Hub</title>
</svelte:head>

<main>
	<!-- Orange band with the pattern (same as login and submit) -->
	<section class="relative overflow-hidden bg-[#FF8C4B] px-4 pb-28 pt-8 text-center md:pb-32 md:pt-12">
		<div
			class="absolute inset-0 opacity-40 mix-blend-multiply"
			style="background-image: url({pattern}); background-size: auto 180px; background-repeat: repeat;"
		></div>

		<div class="relative">
			<h1 class="font-heading text-2xl tracking-wide text-[#2A1A10] sm:text-3xl md:text-5xl">
				SHARE YOUR RECORDS
			</h1>
			<p
				class="mt-4 inline-block rounded-lg bg-[#FFC49B] px-3 py-1.5 text-sm font-semibold text-[#2A1A10] md:px-4 md:py-2 md:text-base"
			>
				Create an account to send links to the Black Cultural Centre for review
			</p>
		</div>
	</section>

	<!-- The card, overlapping the bottom of the band -->
	<div class="relative -mt-20 flex justify-center px-3 pb-16 sm:px-4 md:-mt-24">
		<Card.Root class="w-full max-w-md md:max-w-xl lg:max-w-2xl">
			<Card.Header>
				<Card.Title class="text-2xl">Create account</Card.Title>
				<Card.Description>Sign up with your name, email and a password.</Card.Description>
			</Card.Header>

			<Card.Content>
				<!-- No `action` attribute: posts to the default action in +page.server.ts.
				     novalidate: the server does the checking and shows its messages below each field. -->
				<form method="POST" use:enhance class="space-y-4" novalidate>
					<div class="space-y-2">
						<Label for="name">Name</Label>
						<Input id="name" name="name" autocomplete="name" value={form?.name ?? ''} />
						{#if form?.errors?.name}
							<p class="text-sm font-medium text-[#A84A42]">{form.errors.name[0]}</p>
						{/if}
					</div>

					<div class="space-y-2">
						<Label for="email">Email</Label>
						<Input id="email" name="email" type="email" autocomplete="email" value={form?.email ?? ''} />
						{#if form?.errors?.email}
							<p class="text-sm font-medium text-[#A84A42]">{form.errors.email[0]}</p>
						{/if}
					</div>

					<div class="space-y-2">
						<Label for="password">Password</Label>
						<!-- Never refilled after an error: the server doesn't send the password back -->
						<Input id="password" name="password" type="password" autocomplete="new-password" />
						<p class="text-sm text-muted-foreground">At least 8 characters.</p>
						{#if form?.errors?.password}
							<p class="text-sm font-medium text-[#A84A42]">{form.errors.password[0]}</p>
						{/if}
					</div>

					<div class="flex justify-center pt-2">
						<Button type="submit" class="bg-[#3F6B41] px-10 text-white hover:bg-[#335A35]">
							Create account
						</Button>
					</div>

					<p class="text-center text-sm text-muted-foreground">
						Already have an account? <a href="/login" class="underline">Log in</a>
					</p>
				</form>
			</Card.Content>
		</Card.Root>
	</div>
</main>