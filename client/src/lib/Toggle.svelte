<script lang="ts">
	interface Props {
		textOn: string;
		textOff: string;
		control: boolean;
		fontsize?: string; //'8pt';
	}

	let { textOn, textOff, control = $bindable(true), fontsize = '' }: Props = $props();
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<label class="toggle" style="--fontsize: {fontsize};">
	<input type="checkbox" bind:checked={control} />
	<span class="labels on" data-on={textOn} data-off={textOff}></span>
</label>

<style>
	.toggle {
		position: relative;
		display: inline-block;
		cursor: pointer;
	}

	input {
		display: none;
	}

	.labels {
		font-size: var(--fontsize);
		display: flex;
		align-items: center;
	}

	.labels::after {
		margin-left: 1em;
		content: attr(data-off);
		opacity: 1;
	}

	.labels::before {
		content: attr(data-on);
		opacity: 0.2;
	}

	input:checked ~ .labels::after {
		opacity: 0.2;
	}

	input:checked ~ .labels::before {
		opacity: 1;
	}
</style>
