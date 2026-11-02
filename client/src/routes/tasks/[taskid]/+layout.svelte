<script lang="ts">
    import { page } from "$app/state";

    let { children } = $props();
</script>

<!-- New task id: remount the page, so its state and onMount load start fresh. -->
{#key page.params.taskid}
    {@render children()}
{/key}
