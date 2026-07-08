<script lang="ts">
	import CopyIcon from "@lucide/svelte/icons/copy";
	import { cn } from "$lib/utils";
	import { copyToClipboard } from "$lib/utils/copyToClipboard";
	import type { HTMLButtonAttributes } from "svelte/elements";

	interface Props extends HTMLButtonAttributes {
		text: string;
		ariaLabel?: string;
		iconClass?: string;
		stopPropagation?: boolean;
	}

	let {
		text,
		ariaLabel = "Copy to clipboard",
		iconClass = "size-3",
		stopPropagation = true,
		class: className,
		onclick,
		...restProps
	}: Props = $props();

	async function handleClick(event: MouseEvent) {
		if (stopPropagation) {
			event.stopPropagation();
		}
		await copyToClipboard(text);
		onclick?.(event);
	}

	function handlePointerDown(event: PointerEvent) {
		if (stopPropagation) {
			event.stopPropagation();
		}
	}
</script>

<button
	type="button"
	class={cn("copy-btn", className)}
	aria-label={ariaLabel}
	onclick={handleClick}
	onpointerdown={handlePointerDown}
	{...restProps}
>
	<CopyIcon class={iconClass} />
</button>

<style>
	.copy-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		padding: 0.1rem;
		border-radius: 0.15rem;
		color: inherit;
		opacity: 0.7;
	}

	.copy-btn:hover {
		opacity: 1;
		background-color: rgb(0 0 0 / 0.06);
	}
</style>
