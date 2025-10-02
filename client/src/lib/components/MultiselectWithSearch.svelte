<script lang="ts">
	import * as Command from "$lib/components/ui/command";
	import * as Popover from "$lib/components/ui/popover";
	import { faXmark } from '@fortawesome/free-solid-svg-icons';
	import { tick } from "svelte";
	import Fa from 'svelte-fa';

	type Opt = { name: string; value: string };
	let { options = [], values = $bindable<string[]>([]) }: { options?: Opt[]; values?: string[] } = $props();

	let collapsibleOpen = $state(false);
	let triggerRef: HTMLButtonElement | null = null;

	const valueToOption = $derived(Object.fromEntries(options.map(option => [option.value, option])));
	const selectedOptions = $derived(options.filter(option => values.includes(option.value)));
	const unselectedOptions = $derived(options.filter(option => !values.includes(option.value)));

	function closeAndFocusTrigger() {
		collapsibleOpen = false;
		tick().then(() => {
			triggerRef?.focus();
		});
	}

	function removeValue(value: string) {
		const newValues = values.filter(v => v !== value);
		values = newValues;
	}

	function addValue(value: string) {
		const newValues = [...values, value];
		values = newValues;
	}
</script>

<div class="inline-block">
	<div class="inline-block">
		{#each values as value}
			<div class="inline-block bg-gray-200 rounded-full px-2 py-1 m-1">
				<button onclick={() => removeValue(value)}>
					<Fa class="inline-block hover:cursor-pointer" icon={faXmark} />
				</button>
				{valueToOption[value].name}
			</div>
		{/each}

	</div>
	<Popover.Root bind:open={collapsibleOpen}>
		<Popover.Trigger bind:ref={triggerRef}>
			<button class="inline-block bg-gray-200 rounded-full px-2 py-1 m-1">
			+
			</button>
		</Popover.Trigger>
		<Popover.Content class="w-[200px] p-0">
			<Command.Root>
				<Command.Input placeholder="Search ..." />
				<Command.Empty>No results found.</Command.Empty>
				<Command.Group>
					{#each unselectedOptions as option}
						<Command.Item
							value={option.value}
							onSelect={() => {
								addValue(option.value);
								closeAndFocusTrigger();
							}}
						>
							<!-- <Check class="mr-2 h-4 w-4"/> -->
							{option.name}
						</Command.Item>
					{/each}
				</Command.Group>
			</Command.Root>
		</Popover.Content>
	</Popover.Root>
</div>
