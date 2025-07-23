<script lang="ts">
    import { getContext } from "svelte";
    import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";

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

<div id="main">
    <div class="container">
        <form onsubmit={handleLogin}>
            <label for="username">Username:</label>
            <input
                type="text"
                id="username"
                placeholder="Enter your username"
                bind:value={username}
            />
            <label for="password">Password:</label>
            <input
                type="password"
                id="password"
                placeholder="Enter your password"
                bind:value={password}
            />
            <label for="rememberMe">Remember me:</label>
            <input type="checkbox" id="rememberMe" bind:checked={rememberMe} />
            {#if error}
                <div class="error" style="grid-column: 1 / 3;">{error}</div>
            {/if}
            <div style="grid-column: 1 / 3;">
                <button type="submit">Login</button>
            </div>
        </form>
    </div>
</div>

<style>
    div {
        display: flex;
    }
    #main {
        flex-direction: column;
        align-items: center;
        margin-top: 100px;
    }
    div.container {
        flex: 0;
        align-items: center;
        border: 1px solid #ccc;
        border-radius: 4px;
        padding: 3em;
        box-shadow: 0 0 2em 0 rgba(0, 0, 0, 0.05);
    }
    .error {
        color: red;
        margin: 10px 0;
    }
    form {
        flex: 0;
        display: grid;
        grid-template-columns: 0fr 1fr;
        gap: 0.5em;
    }
    label {
        display: flex;
        align-items: center;
    }
    input {
        padding: 8px;
        border: 1px solid #ccc;
        border-radius: 4px;
    }
    button {
        padding: 10px;
        background-color: #007bff;
        color: white;
        border: none;
        border-radius: 4px;
        cursor: pointer;
    }
    button:hover {
        background-color: #0056b3;
    }
</style>
