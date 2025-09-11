<script lang="ts">
  import { Button } from "$lib/components/ui/button"
  import {
      Command,
      CommandEmpty,
      CommandGroup,
      CommandInput,
      CommandItem,
      CommandList,
  } from "$lib/components/ui/command"
  import {
      Popover,
      PopoverContent,
      PopoverTrigger,
  } from "$lib/components/ui/popover"
  import type { Tag } from "$lib/types"
  
  export let tags: Tag[] = [];
  let value: string
  let open: boolean = true
  function setValue(newValue: string) {
    value = newValue
  }
  function setOpen(newOpen: boolean) {
    open = newOpen
  }
  console.log(tags)
</script>
<div class="main block">
  <Popover portal={window.document.body} open={open} onOpenChange={setOpen}>
    <PopoverTrigger>
      <Button
        variant="outline"
        role="combobox"
        class="w-[200px] justify-between"
      >
        Add tag...
      </Button>
    </PopoverTrigger>
    <PopoverContent class="w-40">
      <Command value={value} onValueChange={setValue}>
        <CommandInput placeholder="Search tags..." />
        <CommandList>
          <CommandEmpty>No tags found.</CommandEmpty>
          <CommandGroup>
            {#each tags as tag}
              <CommandItem
                value={tag.TagName}
                onSelect={(val) => {
                  // console.log(currentValue)
                  setValue(val)
                  setOpen(false)
                }}
              >
                {tag.TagName}
              </CommandItem>
            {/each}
          </CommandGroup>
        </CommandList>
      </Command>
    </PopoverContent>
  </Popover>
</div>