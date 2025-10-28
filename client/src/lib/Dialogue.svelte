<script lang="ts">
	import type { ComponentDef } from "./data/globalContext.svelte";
	import { Button } from "./components/ui/button";
	interface Props {
		content: ComponentDef | string;
		close: () => void;
	}
	let { content, close }: Props = $props();

	function keydown(e: KeyboardEvent) {
		if (e.key == "Escape") {
			close();
		}
	}
</script>

<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
	class="popup"
	tabindex="0"
	onkeydown={keydown}
	onpointerenter={(e) => (e.currentTarget as HTMLElement)?.focus()}
>
	<div class="popup-content">
		{#if typeof content === "string"}
			{content}
			<div class="popup-footer">
				<Button variant="outline" onclick={close}>Close</Button>
			</div>
		{:else}
			<content.component {...content.props} {close} />
		{/if}
	</div>
</div>

<style>
	.popup {
		position: fixed;
		top: 0;
		left: 0;
		width: 100%;
		height: 100%;
		display: flex;
		justify-content: center;
		align-items: center;
		z-index: 1000;
		display: flex;
		flex-direction: column;
	}
	.popup-content {
		background-color: var(--popover);
		color: var(--popover-foreground);

		padding: 1em;

		border-radius: 1em;
		display: flex;
		flex-direction: column;
		align-items: center;

	}
	.popup-footer {
		display: flex;
		padding: 0.5em;
	}
</style>
