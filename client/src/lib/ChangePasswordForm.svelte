<script lang="ts">
    import { getContext } from "svelte";
    import type { GlobalContext } from "$lib/data-loading/globalContext.svelte";

    let password = $state("");
    let newPassword1 = $state("");
    let newPassword2 = $state("");
    let passwordsMatch = $derived(newPassword1 == newPassword2);

    const globalContext = getContext<GlobalContext>("globalContext");
    const { userManager } = globalContext;
    const creator = userManager.creator;

    let changed = $state(false);
    let collapsed = $state(true);
    async function handleSubmit(e: Event) {
        e.preventDefault();
        try {
            await userManager.changePassword(password, newPassword1);
            console.log("Password changed");
            changed = true;
            collapsed = true;
            setTimeout(() => {
                changed = false;
            }, 5000);
        } catch (e) {
            alert("Error changing password");
        }
    }
    
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<h3 onclick={() => (collapsed = !collapsed)}>
    {#if collapsed}
        ▶
    {:else}
        ▼
    {/if}
    Change password
</h3>

{#if changed}
    <div class="changed"><div>Password changed</div></div>
{/if}
<div class="container" class:collapsed>
    <form onsubmit={handleSubmit}>
        <div>
            <label for="username">Username:</label>
            <input
                type="text"
                id="username"
                placeholder="Enter your username"
                value={creator.name}
                disabled
            />
        </div>
        <div>
            <label for="password">Current Password:</label>
            <input
                type="password"
                id="password"
                placeholder="Enter your password"
                bind:value={password}
            />
        </div>
        <div>
            <label for="new_password_1">New Password:</label>
            <input
                type="password"
                id="new_password_1"
                placeholder="Enter your new password"
                bind:value={newPassword1}
                class:invalid={!passwordsMatch}
            />
        </div>
        <div>
            <label for="new_password_2">Repeat New Password:</label>
            <input
                type="password"
                id="new_password_2"
                placeholder="Enter your new password"
                bind:value={newPassword2}
                class:invalid={!passwordsMatch}
            />
        </div>
        <div>
            <button
                type="submit"
                disabled={newPassword1 == "" || !passwordsMatch}
            >
                Change password
            </button>
        </div>
    </form>
</div>

<style>
    h3 {
        cursor: pointer;
    }
    h3:hover {
        text-decoration: underline;
    }
    .container {
        padding: 3em;
        background-color: #e8e8e8;
        border-radius: 10px;
        overflow: hidden;
    }
    form {
        display: flex;
        flex-direction: column;
    }
    div.collapsed {
        display: none;
    }

    form > div {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 10px;
    }

    div {
        margin-bottom: 1em;
    }

    label {
        flex: 1;
        margin-right: 0.5em;
    }

    input {
        flex: 2;
        padding: 8px;
        border: 1px solid #ccc;
        border-radius: 4px;
    }
    input[type="password"].invalid {
        border-color: red;
        background-color: d0ffff;
    }

    button {
        padding: 10px;
        border: none;
        border-radius: 4px;
        background-color: #007bff;
        color: white;
        cursor: pointer;
    }

    button:hover {
        background-color: #0056b3;
    }

    button:disabled,
    button:disabled:hover {
        background-color: gray;
        cursor: default;
    }

    .changed {
        display: flex;
    }
    .changed > div {
        color: #007bff;
        font-weight: bold;
        margin-top: 1em;
    }
</style>
