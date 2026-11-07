<script lang="ts">
	import { fly, fade, slide } from 'svelte/transition';
	import pattern from '#lib/assets/backgroundPattern.webp';

	// Main menu items
	const links = [
		{ label: 'Home', href: '/' },
		{ label: 'Submit request', href: '/login' }
	];

	// Items inside the Admin dropdown
	const adminLinks = [
		{ label: 'Submitted requests', href: '/submitted-requests' },
		{ label: 'Bad links', href: '/bad-links' }
	];

	let menuOpen = $state(false); // is the phone drawer open?
	let adminOpen = $state(false); // is the desktop Admin dropdown open?
	let adminMobileOpen = $state(false); // is Admin open inside the phone drawer?
	let adminMenuEl: HTMLLIElement | undefined = $state();

	// Close the desktop dropdown when clicking anywhere else
	function handleWindowClick(event: MouseEvent) {
		if (adminOpen && adminMenuEl && !adminMenuEl.contains(event.target as Node)) {
			adminOpen = false;
		}
	}

	// Escape closes everything
	function handleKeydown(event: KeyboardEvent) {
		if (event.key === 'Escape') {
			menuOpen = false;
			adminOpen = false;
		}
	}

	// Close the drawer and reset the Admin section inside it
	function closeDrawer() {
		menuOpen = false;
		adminMobileOpen = false;
	}
</script>

<svelte:window onkeydown={handleKeydown} onclick={handleWindowClick} />

<header class="border-b border-orange-100 bg-[#FBF7F2]">
	<nav aria-label="Main" class="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
		<a href="/" class="text-xl font-extrabold tracking-wide">OUR HISTORY HUB</a>

		<!-- BIG SCREENS: links in a row -->
		<ul class="hidden items-center gap-10 font-semibold md:flex">
			{#each links as link}
				<li>
					<a href={link.href} class="hover:text-[#9A3412]">{link.label}</a>
				</li>
			{/each}

			<!-- Admin dropdown -->
			<li class="relative" bind:this={adminMenuEl}>
				<button
					type="button"
					class="flex items-center gap-1 font-semibold hover:text-[#9A3412]"
					aria-haspopup="true"
					aria-expanded={adminOpen}
					aria-controls="admin-menu"
					onclick={() => (adminOpen = !adminOpen)}
				>
					Admin
					<span aria-hidden="true" class="text-xs transition-transform {adminOpen ? 'rotate-180' : ''}">▾</span>
				</button>

				{#if adminOpen}
					<ul
						id="admin-menu"
						class="absolute right-0 top-full z-20 mt-2 w-52 rounded-xl bg-white p-2 shadow-lg"
					>
						{#each adminLinks as link}
							<li>
								<a
									href={link.href}
									class="block rounded-lg px-4 py-3 hover:bg-orange-50"
									onclick={() => (adminOpen = false)}
								>
									{link.label}
								</a>
							</li>
						{/each}
					</ul>
				{/if}
			</li>
		</ul>

		<!-- PHONES: hamburger button -->
		<button
			type="button"
			class="flex h-11 w-11 flex-col items-center justify-center gap-1.5 rounded-lg border border-orange-200 bg-white md:hidden"
			aria-label="Open menu"
			aria-expanded={menuOpen}
			aria-controls="mobile-menu"
			onclick={() => (menuOpen = true)}
		>
			<span class="h-0.5 w-5 bg-[#2A1A10]"></span>
			<span class="h-0.5 w-5 bg-[#2A1A10]"></span>
			<span class="h-0.5 w-5 bg-[#2A1A10]"></span>
		</button>
	</nav>
</header>

<!-- PHONES: the side drawer -->
{#if menuOpen}
	<div class="fixed inset-0 z-40 md:hidden">
		<!-- Dark layer behind the drawer -->
		<button
			type="button"
			class="absolute inset-0 bg-black/40"
			aria-label="Close menu"
			onclick={closeDrawer}
			transition:fade={{ duration: 200 }}
		></button>

		<div
			id="mobile-menu"
			role="dialog"
			aria-modal="true"
			aria-label="Menu"
			class="absolute right-0 top-0 flex h-full w-4/5 max-w-sm flex-col overflow-y-auto bg-[#FBF7F2] shadow-2xl"
			transition:fly={{ x: 400, duration: 250 }}
		>
			<!-- Pattern strip -->
			<div class="relative h-24 shrink-0 bg-[#FF8C4B]">
				<div
					class="absolute inset-0 opacity-70 mix-blend-multiply"
					style="background-image: url({pattern}); background-size: auto 100%; background-repeat: repeat-x;"
				></div>
				<button
					type="button"
					class="absolute right-3 top-3 flex h-11 w-11 items-center justify-center rounded-lg bg-[#FBF7F2] text-2xl font-bold text-[#2A1A10]"
					aria-label="Close menu"
					onclick={closeDrawer}
				>
					&times;
				</button>
			</div>

			<ul class="flex flex-col px-4 py-4 text-lg font-semibold">
				<!-- Home and Submit request -->
				{#each links as link}
					<li>
						<a
							href={link.href}
							class="block border-b border-orange-100 px-2 py-5 hover:text-[#9A3412]"
							onclick={closeDrawer}
						>
							{link.label}
						</a>
					</li>
				{/each}

				<!-- Admin: tap to open its two links -->
				<li>
					<button
						type="button"
						class="flex w-full items-center justify-between border-b border-orange-100 px-2 py-5 text-left font-semibold hover:text-[#9A3412]"
						aria-expanded={adminMobileOpen}
						aria-controls="mobile-admin"
						onclick={() => (adminMobileOpen = !adminMobileOpen)}
					>
						Admin
						<span
							aria-hidden="true"
							class="text-sm transition-transform {adminMobileOpen ? 'rotate-180' : ''}"
						>▾</span>
					</button>

					{#if adminMobileOpen}
						<ul id="mobile-admin" transition:slide={{ duration: 200 }}>
							{#each adminLinks as link}
								<li>
									<a
										href={link.href}
										class="block border-b border-orange-100 py-5 pl-8 pr-2 hover:text-[#9A3412]"
										onclick={closeDrawer}
									>
										{link.label}
									</a>
								</li>
							{/each}
						</ul>
					{/if}
				</li>
			</ul>
		</div>
	</div>
{/if}