<script lang="ts">
	import * as Card from '#lib/components/ui/card/index.js';
	import { Input } from '#lib/components/ui/input/index.js';
	import { Label } from '#lib/components/ui/label/index.js';
	import { Button } from '#lib/components/ui/button/index.js';
	import pattern from '#lib/assets/backgroundPattern.webp';

	let name = $state('');
	let email = $state('');
	let link = $state('');
	let description = $state('');
	let files: FileList | undefined = $state();

	let errors = $state({ name: '', email: '', link: '', description: '' });
	let sent = $state(false);

	const MAX_DESCRIPTION = 500;

	// The name of the chosen document, or empty if none
	let fileName = $derived(files && files.length > 0 ? files[0].name : '');

	function handleSubmit(event: SubmitEvent) {
		event.preventDefault();

		errors = {
			name: name.trim() ? '' : 'Enter your name.',
			email: /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()) ? '' : 'Enter a valid email, like name@example.com',
			link: /^https?:\/\/\S+$/.test(link.trim()) ? '' : 'Enter a full link, starting with https://',
			description: description.trim() ? '' : 'Describe what this link is.'
		};

		if (errors.name || errors.email || errors.link || errors.description) return;

		// TEMPORARY: nothing is saved yet.
		// The team will send this to the database later, as a "pending" request.
		sent = true;
	}

	function sendAnother() {
		name = '';
		email = '';
		link = '';
		description = '';
		files = undefined;
		sent = false;
	}
</script>

<svelte:head>
	<title>Submit a request · Our History Hub</title>
</svelte:head>

<main>
	<!-- Orange band with the pattern -->
	<section class="relative overflow-hidden bg-[#FF8C4B] px-4 pb-28 pt-8 text-center md:pb-32 md:pt-12">
		<div
			class="absolute inset-0 opacity-40 mix-blend-multiply"
			style="background-image: url({pattern}); background-size: auto 180px; background-repeat: repeat;"
		></div>

		<div class="relative">
			<h1 class="text-2xl font-extrabold tracking-wide text-[#2A1A10] sm:text-3xl md:text-5xl">
				SHARE YOUR RECORDS
			</h1>
			<p
				class="mt-4 inline-block rounded-lg bg-[#FFC49B] px-3 py-1.5 text-sm font-semibold text-[#2A1A10] md:px-4 md:py-2 md:text-base"
			>
				Tell us where your records are kept. The Black Cultural Centre will review your request.
			</p>
		</div>
	</section>

	<!-- The form card, overlapping the bottom of the band -->
	<div class="relative -mt-20 flex justify-center px-3 pb-16 sm:px-4 md:-mt-24">
		<Card.Root class="w-full max-w-md md:max-w-xl lg:max-w-2xl">
			{#if sent}
				<!-- What people see after sending -->
				<Card.Header>
					<Card.Title class="text-2xl">Request sent</Card.Title>
					<Card.Description>
						Thank you. The Black Cultural Centre will review your link before it appears in search.
					</Card.Description>
				</Card.Header>
				<Card.Content class="flex justify-center">
					<Button onclick={sendAnother} class="bg-[#3F6B41] px-10 text-white hover:bg-[#335A35]">
						Send another link
					</Button>
				</Card.Content>
			{:else}
				<Card.Header>
					<Card.Title class="text-2xl">Submit a request</Card.Title>
					<Card.Description>Document upload is optional. Everything else is required.</Card.Description>
				</Card.Header>

				<Card.Content>
					<form onsubmit={handleSubmit} class="space-y-5" novalidate>
						<!-- Your name -->
						<div class="space-y-2">
							<Label for="name">Your name</Label>
							<Input
								id="name"
								name="name"
								autocomplete="name"
								bind:value={name}
								aria-invalid={errors.name ? 'true' : undefined}
								aria-describedby={errors.name ? 'name-error' : undefined}
							/>
							{#if errors.name}
								<p id="name-error" class="text-sm font-medium text-[#A84A42]">{errors.name}</p>
							{/if}
						</div>

						<!-- Email -->
						<div class="space-y-2">
							<Label for="email">Email</Label>
							<Input
								id="email"
								name="email"
								type="email"
								autocomplete="email"
								bind:value={email}
								aria-invalid={errors.email ? 'true' : undefined}
								aria-describedby={errors.email ? 'email-error' : undefined}
							/>
							{#if errors.email}
								<p id="email-error" class="text-sm font-medium text-[#A84A42]">{errors.email}</p>
							{/if}
						</div>

						<!-- Link -->
						<div class="space-y-2">
							<Label for="link">Link</Label>
							<Input
								id="link"
								name="link"
								type="url"
								inputmode="url"
								placeholder="https://"
								bind:value={link}
								aria-invalid={errors.link ? 'true' : undefined}
								aria-describedby={errors.link ? 'link-error' : undefined}
							/>
							{#if errors.link}
								<p id="link-error" class="text-sm font-medium text-[#A84A42]">{errors.link}</p>
							{/if}
						</div>

						<!-- Description -->
						<div class="space-y-2">
							<Label for="description">Description</Label>
							<textarea
								id="description"
								name="description"
								rows="5"
								maxlength={MAX_DESCRIPTION}
								bind:value={description}
								aria-invalid={errors.description ? 'true' : undefined}
								aria-describedby="description-help {errors.description ? 'description-error' : ''}"
								class="w-full rounded-md border border-input bg-white px-3 py-2 text-base shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 md:text-sm"
							></textarea>
							<div class="flex justify-between gap-4 text-sm">
								<p id="description-help" class="text-muted-foreground">
									What is it, and what time period or community does it cover?
								</p>
								<p class="shrink-0 text-muted-foreground">{description.length}/{MAX_DESCRIPTION}</p>
							</div>
							{#if errors.description}
								<p id="description-error" class="text-sm font-medium text-[#A84A42]">
									{errors.description}
								</p>
							{/if}
						</div>

						<!-- Bottom row: Doc upload on the left, Submit on the right -->
						<div class="flex flex-wrap items-center justify-between gap-3 pt-2">
							<div class="flex min-w-0 items-center gap-3">
								<label
									for="document"
									class="inline-flex h-9 cursor-pointer items-center rounded-md border border-[#3F6B41] px-4 text-sm font-medium text-[#3F6B41] hover:bg-[#3F6B41]/10 focus-within:ring-[3px] focus-within:ring-ring/50"
								>
									Upload document
									<input
										id="document"
										name="document"
										type="file"
										accept=".pdf"
										class="sr-only"
										bind:files
									/>
								</label>
								<span class="truncate text-sm text-muted-foreground">
									{fileName || 'PDF, optional'}
								</span>
							</div>

							<Button type="submit" class="bg-[#3F6B41] px-8 text-white hover:bg-[#335A35]">
								Submit
							</Button>
						</div>
					</form>
				</Card.Content>
			{/if}
		</Card.Root>
	</div>
</main>