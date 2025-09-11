<script lang="ts">
	import { Button } from "$lib/components/ui/button"
	import * as Command from "$lib/components/ui/command"
	import * as Popover from "$lib/components/ui/popover"
	import { tick } from "svelte"

    let options: {name: string, value: string}[];
    let value: string;

    let collapsibleOpen=false;

    function closeAndFocusTrigger(triggerId: string) {
		collapsibleOpen = false;
		tick().then(() => {
			document.getElementById(triggerId)?.focus();
		});
	}
</script>

<Popover.Root bind:open={collapsibleOpen} let:ids>
    <Popover.Trigger asChild let:builder>
        <Button
        builders={[builder]}
        variant="outline"
        role="combobox"
        class="w-[200px] justify-between"
        >
        {value}
        <!-- <ChevronsUpDown class="ml-2 h-4 w-4 shrink-0 opacity-50" /> -->
        </Button>
    </Popover.Trigger>
    <Popover.Content class="w-[200px] p-0">
        <Command.Root>
            <Command.Input placeholder="Search projects..." />
            <Command.Empty>No framework found.</Command.Empty>
            <Command.Group>
                {#each options as option}
                    <Command.Item
                        value={option.value}
                        onSelect={(currentValue) => {
                            value = currentValue;
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