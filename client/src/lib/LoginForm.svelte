<script lang="ts">
    import { ApiError } from "$lib/api/client";
    import { Button } from "$lib/components/ui/button/index.js";
    import { Checkbox } from "$lib/components/ui/checkbox/index.js";
    import * as Field from "$lib/components/ui/field/index.js";
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import {
        PasswordInput,
        TextInput,
    } from "$lib/components/ui/text-input/index.js";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { getContext, onMount, tick } from "svelte";
    import { authClient } from "../auth";

    const globalContext = getContext<GlobalContext>("globalContext");

    let username = $state("");
    let password = $state("");
    let rememberMe = $state(true);
    let usernameInput = $state<HTMLInputElement | null>(null);
    let passwordInput = $state<HTMLInputElement | null>(null);

    // Empty-field errors appear on submit and clear once the field has text.
    let submitted = $state(false);
    const usernameError = $derived(
        submitted && !username ? "Username is required" : undefined,
    );
    const passwordError = $derived(
        submitted && !password ? "Password is required" : undefined,
    );

    let loginError = $state<{ title: string; subtitle: string } | null>(null);

    async function handlePasswordLogin(e: SubmitEvent) {
        e.preventDefault();
        loginError = null;
        submitted = true;
        if (!username || !password) {
            await tick();
            (username ? passwordInput : usernameInput)?.focus();
            return;
        }
        try {
            await globalContext.userManager.login(
                username,
                password,
                rememberMe,
            );
        } catch (err) {
            loginError =
                err instanceof ApiError && err.status === 401
                    ? {
                          title: "Incorrect username or password",
                          subtitle: "Try again.",
                      }
                    : {
                          title: "Log in failed",
                          subtitle:
                              err instanceof Error ? err.message : String(err),
                      };
            password = "";
            submitted = false;
            // No live role on the notification: Username's aria-describedby
            // reads it when focus lands, after the DOM has updated.
            await tick();
            usernameInput?.focus();
        }
    }

    let oidcError = $state<string | null>(null);
    async function handleOIDCLogin() {
        oidcError = null;
        let authorizeUrl: string;
        try {
            authorizeUrl = (await authClient.OIDCAuthorize()).url;
        } catch (err) {
            oidcError = err instanceof Error ? err.message : String(err);
            return;
        }
        window.location.href = authorizeUrl;
    }

    // Query the API for available authentication options
    let passwordEnabled = $state(false);
    let oidcEnabled = $state(false);
    let oidcProviderName = $state("");
    onMount(async () => {
        const options = await authClient.options();
        passwordEnabled = options.password_enabled;
        oidcEnabled = options.oidc_enabled;
        oidcProviderName = options.oidc_provider_name;
    });
</script>

<!-- Carbon Login pattern, one step, centred. -->
<main class="flex flex-1 justify-center overflow-y-auto px-4">
    <div class="my-auto w-80 py-16">
        <img
            src="/logo-dark.png"
            alt=""
            width="128"
            height="132"
            class="mx-auto mb-12 w-32"
        />
        <h1 class="mb-8 text-heading-03">Log in to EyeNED</h1>

        {#if passwordEnabled}
            <form
                novalidate
                class="flex flex-col gap-6"
                onsubmit={handlePasswordLogin}
            >
                <TextInput
                    labelText="Username"
                    autocomplete="username"
                    bind:value={username}
                    bind:ref={usernameInput}
                    invalidText={usernameError}
                    aria-describedby={loginError ? "login-error" : undefined}
                />
                <PasswordInput
                    labelText="Password"
                    autocomplete="current-password"
                    bind:value={password}
                    bind:ref={passwordInput}
                    invalidText={passwordError}
                />
                <Field.Field orientation="horizontal">
                    <Checkbox id="keep-logged-in" bind:checked={rememberMe} />
                    <Field.Label
                        for="keep-logged-in"
                        class="text-body-compact-01 text-text-primary"
                        >Keep me logged in</Field.Label
                    >
                </Field.Field>
                {#if loginError}
                    <InlineNotification
                        id="login-error"
                        role="none"
                        title={loginError.title}
                        subtitle={loginError.subtitle}
                    />
                {/if}
                <Button type="submit" size="lg" class="w-full">Log in</Button>
            </form>
        {/if}

        {#if oidcEnabled}
            <Button
                size="lg"
                class="mt-6 w-full"
                variant={passwordEnabled ? "outline" : "default"}
                onclick={handleOIDCLogin}>Log in with {oidcProviderName}</Button
            >
            {#if oidcError}
                <InlineNotification
                    class="mt-4"
                    title="Log in failed"
                    subtitle={oidcError}
                />
            {/if}
        {/if}
    </div>
</main>
