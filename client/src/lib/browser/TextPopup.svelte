<script lang="ts">
    interface Props {
        message: string;
    }

    let { message }: Props = $props();
</script>

<div>
	{message}
</div>

<style>
    div {
        background-color: #f4f4f4;
        padding: 2em;
        margin: 2em;
        border: 1px #ccc solid;
        border-radius: 2px;
    }
</style>
