<script lang="ts">
    import type { Snippet } from "svelte";
    interface Props {
        title?: string;
        children?: Snippet;
    }

    let { title = "", children }: Props = $props();
    let collapse = $state(true);
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<div>
    <h2 onclick={() => (collapse = !collapse)}>
        {#if !collapse}
            ▼
        {:else}
            ►
        {/if}
        {title}
    </h2>
    {#if !collapse}
        {@render children?.()}
    {/if}
</div>

<style>
    div {
        border: 1px solid rgba(0, 0, 0, 0.01);
        box-shadow: 0 0 10px rgba(0, 0, 0, 0.05);
        border-radius: 2px;
        margin: 1em;
        padding: 0.5em;
    }
    h2 {
        font-size: large;
        margin: 0;
        cursor: pointer;
    }
    h2:hover {
        background-color: #f9f9f9;
    }
</style>
