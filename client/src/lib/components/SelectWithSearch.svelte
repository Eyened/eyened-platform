<script lang="ts">
	import { Button } from "$lib/components/ui/button";
	import * as Command from "$lib/components/ui/command";
	import * as Popover from "$lib/components/ui/popover";
	import { tick } from "svelte";

	type Props = {
		options: { label: string; value: string }[];
		value?: string;
		placeholder?: string;
		onSelect?: (value: string) => void;
	};

	let { options, value = $bindable(), placeholder = "Select...", onSelect }: Props = $props();

	let collapsibleOpen = $state(false);
	let triggerRef: HTMLButtonElement | null = $state(null);

	function closeAndFocusTrigger() {
		collapsibleOpen = false;
		tick().then(() => {
			triggerRef?.focus();
		});
	}

	const selectedLabel = $derived(
		value ? options.find((option) => option.value === value)?.label : placeholder
	);
</script>

<Popover.Root bind:open={collapsibleOpen}>
	<Popover.Trigger bind:ref={triggerRef}>
		<Button
			variant="outline"
			role="combobox"
			class="w-full justify-between"
		>
			{selectedLabel}
		</Button>
	</Popover.Trigger>
	<Popover.Content class="p-0">
		<Command.Root>
			<Command.Input placeholder={placeholder} />
			<Command.Empty>No results found.</Command.Empty>
			<Command.Group>
				{#each options as option}
					<Command.Item
						value={option.value}
						onSelect={() => {
							value = option.value;
							onSelect?.(option.value);
							closeAndFocusTrigger();
						}}
					>
						{option.label}
					</Command.Item>
				{/each}
			</Command.Group>
		</Command.Root>
	</Popover.Content>
</Popover.Root>