<script lang="ts">
	interface Props {
		map: Map<any, any>;
		value: any;
		displayValueFunction: (value: any) => string;
	}

	let { map, value = $bindable(), displayValueFunction }: Props = $props();
</script>

<select bind:value>
	{#each [...map] as [key, value]}
		<option value={key}>
			{displayValueFunction(value)}
		</option>
	{/each}
</select>
