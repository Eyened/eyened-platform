<script lang="ts">
	import * as Select from "$lib/components/ui/select"
	
	export let options: {label: string | number, value:string | number}[]
    export let selected: string | number | undefined
    export let onSelectedChange: (val: string) => void
    export let disabled: boolean = false
    export let placeholder: string | undefined = undefined

    $: valueToLabel = Object.fromEntries(options.map(opt => [opt.value, opt.label]))

	$: selectedObj = selected
    ? {
        label: valueToLabel[selected],
        value: selected
      }
    : undefined;

    const handleChange : any = (changeObj) => {
        onSelectedChange(changeObj?.value)
    }

</script>


<Select.Root selected={selectedObj} onSelectedChange={handleChange} disabled={disabled}>
    <Select.Trigger class="w-[180px]">
        <Select.Value placeholder={placeholder} />
    </Select.Trigger>
    <Select.Content>
        {#each options as option}
            <Select.Item value={option.value}>{option.label}</Select.Item>
        {/each}        
    </Select.Content>
</Select.Root>