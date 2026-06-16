<script lang="ts">
	type Shortcut = { action: string; keys: string };

	type Section = { title: string; shortcuts: Shortcut[] };

	const sections: Section[] = [
		{
			title: "Navigation",
			shortcuts: [
				{ action: "Pan", keys: "Shift + drag" },
				{ action: "Zoom", keys: "Shift + scroll (or Ctrl / ⌘ + scroll)" },
				{ action: "Reset view", keys: "Escape" },
				{ action: "Hide overlays (hold)", keys: "Space" },
			],
		},
		{
			title: "Image selection",
			shortcuts: [
				{ action: "Open image in main viewer", keys: "Click thumbnail" },
				{ action: "Add image as side panel", keys: "Shift + click thumbnail" },
			],
		},
		{
			title: "OCT volumes",
			shortcuts: [
				{ action: "Previous / next B-scan", keys: "Scroll" },
				{ action: "Previous / next B-scan", keys: "↑ / ↓" },
			],
		},
		{
			title: "Render modes",
			shortcuts: [
				{ action: "Original", keys: "R" },
				{ action: "Luminance", keys: "L" },
				{ action: "Contrast enhanced", keys: "E" },
				{ action: "Color balanced", keys: "B" },
				{ action: "CLAHE", keys: "H" },
				{ action: "Sharpened", keys: "S" },
				{ action: "Histogram matched", keys: "M" },
			],
		},
		{
			title: "Segmentation",
			shortcuts: [
				{ action: "Paint (hold)", keys: "Q" },
				{ action: "Erase (hold)", keys: "W" },
				{
					action: "Pick feature / segmentation under cursor",
					keys: "A",
				},
				{ action: "Set brush radius (1–9)", keys: "1 – 9" },
				{ action: "Increase / decrease brush radius", keys: "+ / −" },
				{ action: "Adjust brush radius", keys: "Alt + scroll" },
				{ action: "Adjust brush radius", keys: "Alt + drag" },
			],
		},
		{
			title: "Registration",
			shortcuts: [
				{ action: "Zoom to registration point", keys: "0 – 9" },
			],
		},
		{
			title: "ETDRS grid",
			shortcuts: [
				{ action: "Cycle central / inner / outer circles", keys: "C / I / O" },
			],
		},
		{
			title: "Panels",
			shortcuts: [
				{ action: "Close overlay", keys: "Escape" },
			],
		},
	];
</script>

<div id="help-overlay">
	<h1>Keyboard shortcuts &amp; interactions</h1>
	<p class="intro">
		Shortcuts apply when the viewer has focus. Some actions only work when the
		relevant tool or panel is active.
	</p>

	{#each sections as section}
		<section>
			<h2>{section.title}</h2>
			<dl>
				{#each section.shortcuts as { action, keys }}
					<div class="row">
						<dt>{action}</dt>
						<dd><kbd>{keys}</kbd></dd>
					</div>
				{/each}
			</dl>
		</section>
	{/each}
</div>

<style>
	div#help-overlay {
		flex: 1;
		padding: 1.5em 2em 3em;
		overflow-y: auto;
		max-width: 42rem;
		margin: 0 auto;
	}

	h1 {
		font-size: 1.5rem;
		font-weight: 600;
		margin: 0 0 0.5em;
	}

	p.intro {
		margin: 0 0 1.5em;
		color: #555;
		font-size: 0.95rem;
		line-height: 1.5;
	}

	section {
		margin-bottom: 1.5em;
	}

	h2 {
		font-size: 1rem;
		font-weight: 600;
		margin: 0 0 0.5em;
		padding-bottom: 0.25em;
		border-bottom: 1px solid #ddd;
	}

	dl {
		margin: 0;
	}

	.row {
		display: grid;
		grid-template-columns: 1fr auto;
		gap: 1em;
		padding: 0.35em 0;
		align-items: baseline;
	}

	dt {
		margin: 0;
		font-size: 0.95rem;
	}

	dd {
		margin: 0;
		text-align: right;
	}

	kbd {
		display: inline-block;
		padding: 0.15em 0.5em;
		font-family: inherit;
		font-size: 0.85rem;
		background: #f3f4f6;
		border: 1px solid #d1d5db;
		border-radius: 4px;
		white-space: nowrap;
	}
</style>
