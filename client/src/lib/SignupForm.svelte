<script lang="ts">
    import { resolve } from "$app/paths";
    import { Button } from "$lib/components/ui/button/index.js";
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import {
        PasswordInput,
        TextInput,
    } from "$lib/components/ui/text-input/index.js";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { getContext, tick } from "svelte";
    import AuthPage from "./AuthPage.svelte";

    const globalContext = getContext<GlobalContext>("globalContext");

    let username = $state("");
    let password = $state("");
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

    const passwordHelp =
        'At least 15 characters. Must not contain your username or "eyened".';

    let signupError = $state<string | null>(null);

    async function handleSubmit(e: SubmitEvent) {
        e.preventDefault();
        signupError = null;
        submitted = true;
        if (!username || !password) {
            await tick();
            (username ? passwordInput : usernameInput)?.focus();
            return;
        }
        try {
            await globalContext.userManager.signup(username, password);
        } catch (err) {
            signupError = err instanceof Error ? err.message : String(err);
            password = "";
            submitted = false;
            // No live role on the notification: Username's aria-describedby
            // reads it when focus lands, after the DOM has updated.
            await tick();
            usernameInput?.focus();
        }
    }
</script>

<AuthPage>
    <div class="mb-8">
        <h1 class="text-heading-03">Create an account</h1>
        <p class="mt-2 text-body-compact-01">
            Already have an account?
            <a
                href={resolve("/users/login")}
                class="text-link-primary underline hover:text-link-primary-hover"
                >Log in</a
            >
        </p>
    </div>
    <form novalidate class="flex flex-col gap-6" onsubmit={handleSubmit}>
        <TextInput
            labelText="Username"
            autocomplete="username"
            bind:value={username}
            bind:ref={usernameInput}
            invalidText={usernameError}
            aria-describedby={signupError ? "signup-error" : undefined}
        />
        <PasswordInput
            labelText="Password"
            autocomplete="new-password"
            helperText={passwordHelp}
            bind:value={password}
            bind:ref={passwordInput}
            invalidText={passwordError}
        />
        {#if signupError}
            <InlineNotification
                id="signup-error"
                role="none"
                title="Account not created"
                subtitle={signupError}
            />
        {/if}
        <Button type="submit" size="lg" class="w-full">Create account</Button>
    </form>
</AuthPage>
