<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { getContext, onMount } from "svelte";
    import { page } from "$app/state";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";

    const globalContext = getContext<GlobalContext>("globalContext");

    let error = $state<string | null>(null);

    async function handleCallback() {
        const code = page.url.searchParams.get("code");
        const state = page.url.searchParams.get("state");

        if (code === null || state === null) {
            error =
                page.url.searchParams.get("error_description") ??
                "Sign-in was cancelled or required parameters are missing.";
            return;
        }

        try {
            await globalContext.userManager.OIDCLogin(code, state);
        } catch (err) {
            error =
                err instanceof Error ? err.message : "Unknown error occurred";
        }
    }

    onMount(() => {
        handleCallback();
    });
</script>

<div class="flex min-h-screen flex-col items-center justify-center p-4">
    <div
        class="m-4 w-[440px] rounded-xl border border-gray-200 bg-white p-8 shadow-sm"
    >
        {#if error}
            <h1 class="mb-2 text-lg font-semibold">Sign-in failed</h1>
            <p class="mb-6 text-sm text-red-600">{error}</p>
            <Button href="/users/login" class="w-full">Back to login</Button>
        {:else}
            <h1 class="mb-2 text-lg font-semibold">Signing in</h1>
            <p class="text-sm text-gray-600">
                Completing OpenID Connect sign-in…
            </p>
        {/if}
    </div>
</div>
