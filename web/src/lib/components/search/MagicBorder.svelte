<script lang="ts">
	import type { Snippet } from 'svelte';

	// Wrap any field: <MagicBorder active={loading}><Input … /></MagicBorder>
	// `rounded` must match the field's own corners, so the ring and glow follow them
	let {
		active = false,
		rounded = 'rounded-md',
		class: className = '',
		children
	}: { active?: boolean; rounded?: string; class?: string; children: Snippet } = $props();
</script>

<!-- Layers, back to front: blurred glow → solid background → the field → gradient ring on top -->
<div class="magic {rounded} {className}" class:active>
	<span class="glow" aria-hidden="true"></span>
	<div class="relative rounded-[inherit] bg-background">
		{@render children()}
	</div>
	<span class="ring" aria-hidden="true"></span>
</div>

<style>
	/* Registering the angle lets the browser animate it smoothly (a plain custom property would jump) */
	@property --magic-angle {
		syntax: '<angle>';
		initial-value: 0deg;
		inherits: false;
	}

	.magic {
		position: relative;
		isolation: isolate; /* keeps the glow's z-index:-1 inside this box, above the page background */
	}

	.glow,
	.ring {
		position: absolute;
		inset: 0;
		border-radius: inherit;
		pointer-events: none;
		/* Defined here, not on .magic: var(--magic-angle) is resolved on the element that declares it,
		   so it must be the same element the animation changes the angle on */
		background: conic-gradient(
			from var(--magic-angle),
			#0a0a0a,
			#3f3f46,
			#7f1d1d,
			#dc2626,
			#f87171,
			#ca8a04,
			#facc15,
			#fde047,
			#4ade80,
			#16a34a,
			#14532d,
			#0a0a0a
		);
		opacity: 0;
		transition: opacity 400ms ease;
	}

	/* Thin, subtle halo just around the edge */
	.glow {
		z-index: -1;
		filter: blur(5px);
	}

	/* Crisp 2px ring: the mask cuts out the middle so only the border shows */
	.ring {
		z-index: 1;
		padding: 2px;
		mask:
			linear-gradient(#000 0 0) content-box exclude,
			linear-gradient(#000 0 0);
	}

	.active .glow,
	.active .ring {
		animation: magic-spin 6s linear infinite;
	}
	.active .glow {
		opacity: 0.3;
	}
	.active .ring {
		opacity: 1;
	}

	@keyframes magic-spin {
		to {
			--magic-angle: 360deg;
		}
	}

	/* No spinning for people who asked for less motion; the colours still show */
	@media (prefers-reduced-motion: reduce) {
		.active .glow,
		.active .ring {
			animation: none;
		}
	}
</style>
