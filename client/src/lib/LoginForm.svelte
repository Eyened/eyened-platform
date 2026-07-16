<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { Checkbox } from "$lib/components/ui/checkbox/index.js";
    import * as Field from "$lib/components/ui/field/index.js";
    import { Input } from "$lib/components/ui/input/index.js";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { getContext, onMount } from "svelte";
    import { authClient } from "../auth";

    const globalContext = getContext<GlobalContext>("globalContext");

    let username = $state("");
    let password = $state("");
    let rememberMe = $state(true);
    let passwordError = $state<string | null>(null);
    async function handlePasswordLogin(e: Event) {
        e.preventDefault();
        if (!username || !password) {
            passwordError = "Please enter both username and password";
            return;
        }
        try {
            await globalContext.userManager.login(
                username,
                password,
                rememberMe,
            );
            passwordError = null;
        } catch (err) {
            passwordError =
                err instanceof Error ? err.message : "Unknown error occurred";
        }
    }

    let oidcError = $state<string | null>(null);
    async function handleOIDCLogin(e: Event) {
        e.preventDefault();
        let authorizeUrl = "";
        try {
            let resp = await authClient.OIDCAuthorize();
            authorizeUrl = resp.url;
        } catch (err) {
            oidcError =
                err instanceof Error ? err.message : "Unknown error occurred";
        }

        // Redirect the browser to the OIDC authorize URL
        window.location.href = authorizeUrl;
    }

    // Query the API for available authentication options
    let passwordModalEnabled = $state(false);
    let oidcModalEnabled = $state(false);
    let oidcProviderName = $state("");
    async function getAuthOptions() {
        let options = await authClient.options();
        passwordModalEnabled = options.password_enabled;
        oidcModalEnabled = options.oidc_enabled;
        oidcProviderName = options.oidc_provider_name;
    }
    onMount(() => {
        getAuthOptions();
    });
</script>

<div class="flex min-h-screen flex-col items-center justify-center p-4">
    {#if passwordModalEnabled}
        <div
            class="m-4 w-[440px] rounded-xl border border-gray-200 bg-white p-8 shadow-sm"
        >
            <form onsubmit={handlePasswordLogin} class="space-y-6">
                <Field.Set>
                    <Field.Group>
                        <Field.Field>
                            <Field.Label for="username">Username</Field.Label>
                            <Input
                                id="username"
                                type="text"
                                placeholder="Enter your username"
                                bind:value={username}
                            />
                        </Field.Field>

                        <Field.Field>
                            <Field.Label for="password">Password</Field.Label>
                            <Input
                                id="password"
                                type="password"
                                placeholder="Enter your password"
                                bind:value={password}
                            />
                        </Field.Field>

                        <Field.Field>
                            <div class="flex items-center gap-2">
                                <Checkbox
                                    id="rememberMe"
                                    bind:checked={rememberMe}
                                />
                                <Field.Label
                                    for="rememberMe"
                                    class="cursor-pointer select-none"
                                    >Remember me</Field.Label
                                >
                            </div>
                        </Field.Field>
                    </Field.Group>
                </Field.Set>

                {#if passwordError}
                    <p class="text-sm text-red-600">{passwordError}</p>
                {/if}

                <Button type="submit" class="w-full">Login</Button>
            </form>
        </div>
    {/if}

    {#if oidcModalEnabled}
        <div
            class="m-4 w-[440px] rounded-xl border border-gray-200 bg-white p-8 shadow-sm"
        >
            <Button class="w-full" onclick={handleOIDCLogin}
                >Login with {oidcProviderName}</Button
            >

            {#if oidcError}
                <p class="text-sm text-red-600">{oidcError}</p>
            {/if}
        </div>
    {/if}
</div>

<style>
</style>
