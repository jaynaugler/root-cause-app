<script lang="ts">
	import { enhance } from '$app/forms';
	import { Button } from '#lib/components/ui/button/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Label } from '#lib/components/ui/label/index.js';
	import * as Card from '#lib/components/ui/card/index.js';
	import type { PageProps } from './$types';

	// `form` = whatever the action returned: fail(400, {...}) data, or undefined.
	let { form }: PageProps = $props();
</script>

<svelte:head>
	<title>Create account</title>
</svelte:head>

<main class="container mx-auto max-w-md px-4 py-12">
	<Card.Root>
		<Card.Header>
			<Card.Title>Create account</Card.Title>
			<Card.Description>Sign up with your name, email and a password.</Card.Description>
		</Card.Header>
		<Card.Content>
			<!-- No `action` attribute: posts to the default action in +page.server.ts -->
			<form method="POST" use:enhance class="space-y-4">
				<div class="space-y-2">
					<Label for="name">Name</Label>
					<Input id="name" name="name" autocomplete="name" required value={form?.name ?? ''} />
					{#if form?.errors?.name}
						<p class="text-sm font-medium text-red-500">{form.errors.name[0]}</p>
					{/if}
				</div>

				<div class="space-y-2">
					<Label for="email">Email</Label>
					<Input
						id="email"
						name="email"
						type="email"
						autocomplete="email"
						required
						value={form?.email ?? ''}
					/>
					{#if form?.errors?.email}
						<p class="text-sm font-medium text-red-500">{form.errors.email[0]}</p>
					{/if}
				</div>

				<div class="space-y-2">
					<Label for="password">Password</Label>
					<!-- Never refilled after an error: the server doesn't send the password back -->
					<Input
						id="password"
						name="password"
						type="password"
						autocomplete="new-password"
						required
						minlength={8}
					/>
					{#if form?.errors?.password}
						<p class="text-sm font-medium text-red-500">{form.errors.password[0]}</p>
					{/if}
				</div>

				<Button type="submit" class="w-full">Create account</Button>
			</form>
		</Card.Content>
		<Card.Footer class="text-sm text-muted-foreground">
			Already have an account?&nbsp;<a href="/login" class="underline">Log in</a>
		</Card.Footer>
	</Card.Root>
</main>
