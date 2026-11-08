<script lang="ts">
	import { Button } from '#lib/components/ui/button/index.js';
	import pattern from '#lib/assets/backgroundPattern.webp';
	import GreenPattern from '#lib/assets/GreenPattern.jpg';

	import portiaPhoto from '#lib/assets/people/portia-white.webp';
	import portiaFace from '#lib/assets/people/portia-white-face.webp';
	import hallPhoto from '#lib/assets/people/william-hall.webp';
	import hallFace from '#lib/assets/people/william-hall-face.webp';
	import bestPhoto from '#lib/assets/people/carrie-best.webp';
	import bestFace from '#lib/assets/people/carrie-best-face.webp';
	import desmondPhoto from '#lib/assets/people/viola-desmond.webp';
	import desmondFace from '#lib/assets/people/viola-desmond-face.webp';
	import crawfordPhoto from '#lib/assets/people/carl-crawford.webp';
	import crawfordFace from '#lib/assets/people/carl-crawford-face.webp';

	// The colour sets from the BCC banners: banner colour, darker pattern colour,
	// name box colour and text, and the small strip with the person's role.
	// All name boxes are yellow, so they match.
	const COLOURS = {
		red: { banner: '#A84A42', dark: '#6E2420', box: '#F2C75C', boxText: '#5A1A14', role: '#E2B24A', roleText: '#5A1A14' },
		green: { banner: '#4A7A4C', dark: '#2C4E2E', box: '#F2C75C', boxText: '#1F3A21', role: '#E2B24A', roleText: '#1F3A21' },
		blue: { banner: '#4C64A8', dark: '#2B3D73', box: '#F2C75C', boxText: '#4A1E10', role: '#E2B24A', roleText: '#4A1E10' }
	} as const;

	// The people, in the order they appear.
	// Descriptions are copied word for word from the BCC exhibit banners.
	const people = [
		{
			name: 'Portia May White',
			years: '1911–1968',
			role: 'Singer / Chanteuse',
			colour: 'red',
			photo: portiaPhoto,
			face: portiaFace,
			description: `Renowned contralto Portia White was born in Truro, began to sing in the church choir, and went on to become one of the greatest vocalists in Canadian history. When Portia was six, her family moved to Halifax where her father, Rev. William A. White was the pastor at Cornwallis Street Baptist Church. At the time it was not common for young Black girls to aspire to sing classical music, yet that is exactly what Portia wanted to do and what she achieved. She also became a school teacher. Her first major concert was held in Toronto in 1941, when Portia was thirty, and by 1944, she was touring internationally. Her professional development was greatly aided by the Nova Scotia government, which established a fund to that end. That Nova Scotia Talent Trust, initiated to assist Portia, still exists. In the 1950s, Portia White gave a command performance for Queen Elizabeth II. Later in life, Portia lived in Toronto and became a voice teacher to younger talents, such as Maureen Forrester and Robert Goulet. In 1998, the Nova Scotia Arts Council established a Portia White Prize to recognize cultural and artistic excellence. Canada Post issued a postage stamp in her honour in 1999 while the Government of Canada declared her a person of national significance in 1995.`
		},
		{
			name: 'William Hall',
			years: '1827–1904',
			role: 'Military Service / Service militaire',
			colour: 'green',
			photo: hallPhoto,
			face: hallFace,
			description: `A native of Summerville, Hants County, William Hall was the first Black, the first Nova Scotian, and the third Canadian to receive the Victoria Cross, the highest honour in the British military. Hall began his seafaring career at a young age and later enlisted in the British Royal Navy as an able seaman. The era was one of a far-flung British Empire and Hall was decorated with British and Turkish medals for his service in the Crimean War. Then, in 1857, while serving on the HMS Shannon, William Hall volunteered with a relief force sent to Lucknow, India, where a British garrison was besieged by mutineers. He was one of only two men to survive the attack. Hall continued to fight until the relief of the garrison was assured. For his outstanding bravery he was awarded the Victoria Cross. In 2008, William Hall was declared a person of national significance and in 2010 Canada Post honoured his memory with a stamp.`
		},
		{
			name: 'Dr. Carrie Best',
			years: '1903–2001',
			role: 'Journalist / Journaliste',
			colour: 'blue',
			photo: bestPhoto,
			face: bestFace,
			description: `Born in New Glasgow and raised in Tracadie, Carrie Best came into a world where the odds were stacked against a woman of colour. Throughout her life, working as a teacher, poet, author and journalist, she was a fearless activist who brought positive change. In 1946, she established The Clarion, one of Nova Scotia's first newspapers for Black Canadians. Best lobbied the Nova Scotia government to repeal its segregation laws, which it did in 1954. She also had a radio show and a newspaper column to speak out against discrimination. Later in life, Carrie Best received honourary doctorates and the Queen Elizabeth Medal. Other forms of recognition included two Order of Canada designations (she was made a Member in 1974 and an Officer in 1979). Dr. Carrie Best's memory was honoured by a stamp issued by Canada Post in 2011.`
		},
		{
			name: 'Viola Davis Desmond',
			years: '1914–1965',
			role: 'Civil Rights / Droits civils',
			colour: 'red',
			photo: desmondPhoto,
			face: desmondFace,
			description: `The story of Viola Desmond (née Davis) is already summarized on a lower level banner, but it deserves repeating up here. That's because the story of this Halifax-born business woman was one of the most publicized incidents of racial discrimination in Nova Scotian and Canadian history. In November 1946, Viola wanted to go to the movies in New Glasgow while her car was being serviced. She decided she would sit not in the balcony – where Blacks were “supposed” to sit – but rather on the ground floor which was for Whites only. Her courageous challenge to segregation attitudes and policies of the time ended up in court. Viola Desmond deliberately provoked an incident that would become a turning point in the fight against discriminatory practices in Canada. In 2010, Lt. Gov. Mayann Francis issued a posthumous pardon to Viola Desmond for the conviction she had wrongly been given.`
		},
		{
			name: 'Carl "Campy" Crawford',
			years: 'c. 1932–2003',
			role: 'Police & Community / Police & Communauté',
			colour: 'blue',
			photo: crawfordPhoto,
			face: crawfordFace,
			description: `When Carl “Campy” Crawford passed away in 2003, the entire Cape Breton Regional Municipality mourned. That's because Carl was no ordinary man. After growing up in Whitney Pier, Carl was a pioneer in 1964 when he became the first Black municipal police officer east of Montreal. In the years that followed, his friendly demeanour while patrolling Sydney's streets and the helpful approach he had toward life made him a role model to many. He went out of his way to be a force and an example for good. His nickname, Campy, came from the fact that Carl was a terrific catcher in baseball, as was his hero in the big leagues when he was a kid, Roy “Campy” Campanella. Since his passing the Cape Breton Regional Municipality has established the Carl “Campy” Crawford Leadership Award in his honour and memory.`
		}
	] as const;

	let selected = $state(0); // which person is chosen (starts with the first one)
	let person = $derived(people[selected]);
	let c = $derived(COLOURS[person.colour]);
	let aboutEl: HTMLElement | undefined = $state();

	function choose(i: number) {
		selected = i;
		aboutEl?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
	}
</script>

<svelte:head>
	<title>Learning · Our History Hub</title>
</svelte:head>

<main>
	<!-- Orange hero with the pattern, holding only the people -->
	<section class="relative overflow-hidden bg-[#FF8C4B]" aria-label="People in our history">
		<div
			class="absolute inset-0 opacity-40 mix-blend-multiply"
			style="background-image: url({pattern}); background-size: auto 180px; background-repeat: repeat;"
		></div>

		<!-- BIG SCREENS: tall banners, with space around them -->
		<div class="relative mx-auto hidden max-w-7xl justify-center gap-6 px-10 py-14 md:flex lg:gap-8 lg:px-16">
			{#each people as p, i}
				{@const pc = COLOURS[p.colour]}
				<button
					type="button"
					class="banner"
					style="--banner: {pc.banner}; --dark: {pc.dark};"
					aria-pressed={selected === i}
					onclick={() => choose(i)}
				>
					<span class="band"></span>
					<!-- Name box: fixed height, so every banner's box is the same size -->
					<span
						class="flex h-24 flex-col items-center justify-center px-2 text-center font-serif"
						style="background: {pc.box}; color: {pc.boxText};"
					>
						<span class="text-sm font-bold uppercase leading-tight tracking-wider lg:text-base">{p.name}</span>
						<span class="mt-1 text-xs lg:text-sm">{p.years}</span>
					</span>
					<!-- Role strip: fixed height too -->
					<span
						class="flex h-10 items-center justify-center px-2 text-center text-[10px] font-semibold italic leading-tight lg:text-[11px]"
						style="background: {pc.role}; color: {pc.roleText};"
					>
						{p.role}
					</span>
					<span class="band"></span>
					<span class="photo">
						<img src={p.photo} alt="" class="h-full w-full object-cover object-top mix-blend-multiply" />
					</span>
				</button>
			{/each}
		</div>

		<!-- PHONES: round portraits you can swipe -->
		<div class="relative flex gap-4 overflow-x-auto px-4 py-6 md:hidden">
			{#each people as p, i}
				{@const pc = COLOURS[p.colour]}
				<button
					type="button"
					class="circle flex w-20 shrink-0 flex-col items-center"
					aria-pressed={selected === i}
					onclick={() => choose(i)}
				>
					<span class="ring block h-16 w-16 overflow-hidden rounded-full" style="background: {pc.banner};">
						<img src={p.face} alt="" class="h-full w-full object-cover mix-blend-multiply" />
					</span>
					<span class="mt-2 text-center text-xs font-bold leading-tight text-[#2A1A10]">{p.name}</span>
				</button>
			{/each}
		</div>
	</section>

	<!-- About the chosen person: styled like the back of a BCC banner -->
	<section bind:this={aboutEl} aria-live="polite" class="mx-auto my-10 max-w-6xl px-3 sm:px-4">
		<article
			class="overflow-hidden rounded-2xl border border-orange-100 bg-white shadow-sm"
			style="--banner: {c.banner}; --dark: {c.dark};"
		>
			<!-- Coloured top, like the top of the banner -->
			<div style="background: {c.banner};">
				<span class="band"></span>
				<div class="flex flex-col items-center gap-5 px-6 py-6 sm:flex-row sm:items-end md:px-10">
					<!-- Small portrait -->
					<div
						class="isolate aspect-[4/5] w-36 shrink-0 overflow-hidden rounded-xl ring-4 ring-white/25 md:w-44"
						style="background: {c.banner};"
					>
						<img
							src={person.photo}
							alt="Portrait of {person.name}"
							class="h-full w-full object-cover object-top mix-blend-multiply"
						/>
					</div>

					<!-- Name box and role, like on the banner -->
					<div class="text-center sm:text-left">
						<div class="inline-block rounded-md px-4 py-2 font-serif" style="background: {c.box}; color: {c.boxText};">
							<h1 class="text-2xl font-bold uppercase tracking-wider md:text-3xl">{person.name}</h1>
							<p>{person.years}</p>
						</div>
						<p class="mt-3">
							<span
								class="inline-block rounded px-3 py-1 text-sm font-semibold italic"
								style="background: {c.role}; color: {c.roleText};"
							>
								{person.role}
							</span>
						</p>
					</div>
				</div>
				<span class="band"></span>
			</div>

			<!-- The description -->
			<div class="px-6 py-8 md:px-10">
				<p class="description leading-relaxed text-[#2A1A10] lg:columns-2 lg:gap-12">{person.description}</p>

				<!-- Bottom row: credit on the left, button on the right -->
				<div class="mt-8 flex flex-col gap-4 border-t border-orange-100 pt-5 md:flex-row md:items-end md:justify-between">
					<p class="text-xs text-muted-foreground">Text from the Black Cultural Centre for Nova Scotia exhibit.</p>
					<div class="md:text-right">
						<p class="text-sm text-[#2A1A10]">Want to learn more about {person.name}?</p>
						<Button
							href="/"
							class="relative mt-2 inline-flex h-10 overflow-hidden bg-card-btn p-0 pl-10 text-white hover:bg-card-btn-hover"
						>
							<img src={GreenPattern} alt="" class="absolute left-0 top-0 size-10 rounded-l-md object-cover" />
							<span class="px-4">Search the records</span>
						</Button>
					</div>
				</div>
			</div>
		</article>
	</section>
</main>

<style>
	/* One tall banner, like the ones in the BCC rotunda */
	.banner {
		display: flex;
		flex-direction: column;
		flex: 0 1 210px;
		min-width: 0;
		height: 460px;
		overflow: hidden;
		border-radius: 14px;
		background: var(--banner);
		isolation: isolate;
		cursor: pointer;
		transition: transform 0.2s, box-shadow 0.2s;
	}
	.banner:hover {
		transform: translateY(-6px);
		box-shadow: 0 12px 22px rgb(42 26 16 / 0.25);
	}
	.banner[aria-pressed='true'],
	.banner:focus-visible {
		outline: 4px solid #2a1a10;
		outline-offset: 4px;
	}

	/* The thin zigzag band (used on the banners and the person section) */
	.band {
		display: block;
		height: 12px;
		flex-shrink: 0;
		background:
			linear-gradient(135deg, var(--dark) 25%, transparent 25%) -6px 0 / 12px 12px,
			linear-gradient(225deg, var(--dark) 25%, transparent 25%) -6px 0 / 12px 12px,
			var(--banner);
	}

	.photo {
		display: block;
		flex: 1;
		min-height: 0;
	}

	/* Phone circles */
	.ring {
		isolation: isolate;
		box-shadow: 0 0 0 2px #ff8c4b, 0 0 0 4px #ffc49b;
		transition: transform 0.15s;
	}
	.circle[aria-pressed='true'] .ring {
		box-shadow: 0 0 0 3px #ff8c4b, 0 0 0 6px #2a1a10;
	}
	.circle:active .ring {
		transform: scale(0.92);
	}

	/* A big first letter in the banner colour, like a book or magazine */
	.description::first-letter {
		float: left;
		margin: 0.35rem 0.5rem 0 0;
		font-family: Georgia, serif;
		font-size: 3.2rem;
		font-weight: 700;
		line-height: 0.85;
		color: var(--banner);
	}

	@media (prefers-reduced-motion: reduce) {
		.banner,
		.ring {
			transition: none;
		}
	}
</style>