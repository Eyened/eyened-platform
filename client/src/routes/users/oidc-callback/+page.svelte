<script lang="ts">
    import { resolve } from "$app/paths";
    import { page } from "$app/state";
    import AuthPage from "$lib/AuthPage.svelte";
    import { InlineLoading } from "$lib/components/ui/inline-loading/index.js";
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { getContext, onMount } from "svelte";

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

<AuthPage>
    <h1 class="mb-8 text-heading-03">Log in to EyeNED</h1>
    {#if error}
        <InlineNotification title="Log in failed" subtitle={error} />
        <a
            href={resolve("/users/login")}
            class="mt-6 inline-block text-body-compact-01 text-link-primary hover:text-link-primary-hover hover:underline"
            >Back to log in</a
        >
    {:else}
        <InlineLoading status="active" description="Logging in…" />
    {/if}
</AuthPage>
