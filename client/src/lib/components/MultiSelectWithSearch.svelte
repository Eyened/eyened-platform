<script lang="ts">
    import * as Command from "$lib/components/ui/command"
    import * as Popover from "$lib/components/ui/popover"
    import { faXmark } from '@fortawesome/free-solid-svg-icons'
    import { createEventDispatcher, tick } from "svelte"
    import Fa from 'svelte-fa'

    export let options: {name: string, value: string}[] = [];
    export let values: string[] = [];

    let collapsibleOpen=false;

    const dispatch = createEventDispatcher<{change: string[]}>()


    let valueToOption: {[key: string]: {name: string, value: string}} = {};
    $: valueToOption = Object.fromEntries(options.map(option => [option.value, option]));

    let selectedOptions
    $: selectedOptions = options.filter(option => values.includes(option.value));
    $: unselectedOptions = options.filter(option => !values.includes(option.value));

    function closeAndFocusTrigger(triggerId: string) {
		collapsibleOpen = false;
		tick().then(() => {
			document.getElementById(triggerId)?.focus();
		});
	}
</script>

<div class="inline-block">
    <div class="inline-block">
        {#each values as value}
            <div class="inline-block bg-gray-200 rounded-full px-2 py-1 m-1">
                <button on:click={()=>{
                    dispatch('change', values.filter(v => v !== value));
                }}>
                    <Fa class="inline-block hover:cursor-pointer" icon={faXmark} />
                </button>
                {valueToOption[value].name}
            </div>
        {/each}
        
    </div>
    <Popover.Root bind:open={collapsibleOpen} let:ids>
        <Popover.Trigger>
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
                            onSelect={(currentValue) => {
                                dispatch('change', [...values, currentValue]);
                                closeAndFocusTrigger(ids.trigger);
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