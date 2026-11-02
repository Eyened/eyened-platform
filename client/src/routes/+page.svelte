<script lang="ts">
    import Browser from "$lib/browser/Browser.svelte";
    import Main from "../lib/components/Main.svelte";
</script>

<svelte:head>
    <title>Eyened browser</title>
</svelte:head>

<Main>
    <Browser />
</Main>

<!-- <Browser /> -->

<style>
    :global(canvas) {
        position: absolute;
        left: 0;
        top: 0;
        bottom: 0;
        right: 0;
    }
</style>
