<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { Checkbox } from "$lib/components/ui/checkbox/index.js";
    import * as Field from "$lib/components/ui/field/index.js";
    import { Input } from "$lib/components/ui/input/index.js";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { getContext } from "svelte";

    const globalContext = getContext<GlobalContext>("globalContext");

    let username = $state("");
    let password = $state("");
    let error = $state<string | null>(null);
    let rememberMe = $state(true);
    async function handleLogin(e: Event) {
        e.preventDefault();
        if (!username || !password) {
            error = "Please enter both username and password";
            return;
        }
        try {
            await globalContext.userManager.login(
                username,
                password,
                rememberMe,
            );
            error = null;
        } catch (err) {
            error =
                err instanceof Error ? err.message : "Unknown error occurred";
        }
    }
</script>

<div class="min-h-screen flex items-center justify-center p-4">
    <div class="w-[440px] border border-gray-200 rounded-xl shadow-sm p-8 bg-white">
        <form onsubmit={handleLogin} class="space-y-6">
            <Field.Set>
                <Field.Group>
                    <Field.Field>
                        <Field.Label for="username">Username</Field.Label>
                        <Input id="username" type="text" placeholder="Enter your username" bind:value={username} />
                    </Field.Field>

                    <Field.Field>
                        <Field.Label for="password">Password</Field.Label>
                        <Input id="password" type="password" placeholder="Enter your password" bind:value={password} />
                    </Field.Field>

                    <Field.Field>
                        <div class="flex items-center gap-2">
                            <Checkbox id="rememberMe" bind:checked={rememberMe} />
                            <Field.Label for="rememberMe" class="cursor-pointer select-none">Remember me</Field.Label>
                        </div>
                    </Field.Field>
                </Field.Group>
            </Field.Set>

            {#if error}
                <p class="text-sm text-red-600">{error}</p>
            {/if}

            <Button type="submit" class="w-full">Login</Button>
        </form>
    </div>
</div>

<style>
</style>
