<script lang="ts">
	import { fly, fade } from 'svelte/transition';
	import pattern from '#lib/assets/backgroundPattern.webp';

	const links = [
		{ label: 'Search', href: '/' },
		{ label: 'People', href: '/people' },
		{ label: 'Submit a resource', href: '/submit' },
		{ label: 'About', href: '/about' }
	];

	let menuOpen = $state(false);
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && (menuOpen = false)} />

<header class="border-b border-orange-100 bg-[#FBF7F2]">
	<nav aria-label="Main" class="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
		<a href="/" class="text-xl font-extrabold tracking-wide">OUR HISTORY HUB</a>

		<!-- Links in a row: only on bigger screens -->
		<ul class="hidden gap-6 font-semibold md:flex">
			{#each links as link}
				<li>
					<a href={link.href} class="hover:text-[#9A3412]">{link.label}</a>
				</li>
			{/each}
		</ul>

		<!-- Hamburger button: only on phones -->
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

<!-- The side drawer: only exists when menuOpen is true -->
{#if menuOpen}
	<div class="fixed inset-0 z-40 md:hidden">
		<!-- Dark see-through layer behind the drawer. Tapping it closes the menu. -->
		<button
			type="button"
			class="absolute inset-0 bg-black/40"
			aria-label="Close menu"
			onclick={() => (menuOpen = false)}
			transition:fade={{ duration: 200 }}
		></button>

		<!-- The drawer itself -->
		<div
			id="mobile-menu"
			role="dialog"
			aria-modal="true"
			aria-label="Menu"
			class="absolute right-0 top-0 flex h-full w-4/5 max-w-sm flex-col bg-[#FBF7F2] shadow-2xl"
			transition:fly={{ x: 400, duration: 250 }}
		>
			<!-- Pattern strip at the top -->
			<div class="relative h-24 bg-[#FF8C4B]">
				<div
					class="absolute inset-0 opacity-70 mix-blend-multiply"
					style="background-image: url({pattern}); background-size: auto 100%; background-repeat: repeat-x;"
				></div>

				<!-- Close (X) button -->
				<button
					type="button"
					class="absolute right-3 top-3 flex h-11 w-11 items-center justify-center rounded-lg bg-[#FBF7F2] text-2xl font-bold text-[#2A1A10]"
					aria-label="Close menu"
					onclick={() => (menuOpen = false)}
				>
					&times;
				</button>
			</div>

			<!-- Menu links -->
			<ul class="flex flex-col px-4 py-4 text-lg font-semibold">
				{#each links as link}
					<li>
						<a
							href={link.href}
							class="block border-b border-orange-100 px-2 py-4 hover:text-[#9A3412]"
							onclick={() => (menuOpen = false)}
						>
							{link.label}
						</a>
					</li>
				{/each}
			</ul>
		</div>
	</div>
{/if}