<script lang="ts">
	import * as Select from "$lib/components/ui/select"

    interface Props {
        options: {label: string | number, value:string}[]
        value: string | undefined
        disabled: boolean
        placeholder: string | undefined
    }   
	
    let {options, value=$bindable(), disabled, placeholder}: Props = $props()
    
    const valueToLabel = $derived(Object.fromEntries(options.map(opt => [opt.value, opt.label])))

    // $: valueToLabel = Object.fromEntries(options.map(opt => [opt.value, opt.label]))

	// $: selectedObj = selected
    // ? {
    //     label: valueToLabel[selected],
    //     value: selected
    //   }
    // : undefined;

    // const handleChange : any = (changeObj) => {
    //     onSelectedChange(changeObj?.value)
    // }

</script>


<Select.Root type="single" bind:value disabled={disabled}>
    <Select.Trigger>
        {value ? valueToLabel[value] : placeholder}
    </Select.Trigger>
    <Select.Content>
        {#each options as option}
            <Select.Item value={option.value}>{option.label}</Select.Item>
        {/each}        
    </Select.Content>
</Select.Root>