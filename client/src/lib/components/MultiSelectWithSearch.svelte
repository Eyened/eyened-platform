<script lang="ts">
    import * as Command from "$lib/components/ui/command";
    import * as Popover from "$lib/components/ui/popover";
    import { faXmark } from '@fortawesome/free-solid-svg-icons';
    import { tick } from "svelte";
    import Fa from 'svelte-fa';

    type Props = {
        options: { label: string; value: string }[];
        values?: string[];
        onselect?: (values: string[]) => void;
    };

    let { options, values = $bindable(), onselect }: Props = $props();


    let collapsibleOpen = $state(false);
	let triggerRef: HTMLButtonElement | null = $state(null);

    const selectedValues = $derived(values ?? []);
    const valueToOption = $derived(Object.fromEntries(options.map(option => [option.value, option])));
    const unselectedOptions = $derived(options.filter(option => !selectedValues.includes(option.value)));

    function closeAndFocusTrigger() {
        collapsibleOpen = false;
        tick().then(() => {
            triggerRef?.focus();
        });
    }

    function removeValue(valueToRemove: string) {
        values = selectedValues.filter(v => v !== valueToRemove);
        onselect?.(values);
    }

    function addValue(valueToAdd: string) {
        values = [...selectedValues, valueToAdd];
        onselect?.(values);
    }
</script>
<div class="inline-block">
    <div class="inline-block">
        {#each selectedValues as value}
            <div class="inline-block bg-gray-200 rounded-full px-2 py-1 m-1">
                <button onclick={() => removeValue(value)}>
                    <Fa class="inline-block hover:cursor-pointer" icon={faXmark} />
                </button>
                {valueToOption[value]?.label || value}
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
                <Command.List class="max-h-[140px] overflow-y-auto">
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
                                    {option.label}
                                </Command.Item>
                            {/each}
                        </Command.Group>
                </Command.List>
            </Command.Root>
        </Popover.Content>
    </Popover.Root>
</div>