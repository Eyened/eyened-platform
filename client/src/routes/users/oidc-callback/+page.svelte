<script lang="ts">
    import {getContext, onMount} from 'svelte';
    import { page } from '$app/state';
    import type {GlobalContext} from "$lib/data/globalContext.svelte";

    const globalContext = getContext<GlobalContext>("globalContext");

    let error = '';

    async function handleCallback() {
        let code = page.url.searchParams.get('code');
        let state = page.url.searchParams.get('state');

        if (code === null || state === null) {
            error = "One or more required parameters (code, state) are missing";
            return;
        }
        try {
            await globalContext.userManager.OIDCLogin(code, state);
        } catch (err) {
            error = err instanceof Error ? err.message : "Unknown error occurred";
        }
    }

    onMount(() => {
        handleCallback();
    });
</script>

{#if error }
    <h1>OIDC callback</h1>
    <p class="text-sm text-red-600">Error: {error}</p>
    <p><a href="/">Return to front page</a></p>
{/if}
