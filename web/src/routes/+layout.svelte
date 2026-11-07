<script lang="ts">
	import './layout.css';
	import favicon from '#lib/assets/favicon.svg';
	import Header from '#lib/components/site/Header.svelte';
	import Footer from '#lib/components/site/Footer.svelte'; // NEW
	import type { LayoutProps } from './$types';

	let { children }: LayoutProps = $props();
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
</svelte:head>

<div class="flex min-h-screen flex-col"> <!-- NEW -->
	<Header />

	<div class="flex-1"> <!-- NEW -->
		{@render children()}
	</div>

	<Footer /> <!-- NEW -->
</div>