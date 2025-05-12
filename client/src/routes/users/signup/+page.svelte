<script lang="ts">
    import { globalContext } from "$lib/main";

    const userManager = globalContext.userManager;

    let username = $state("");
    let password = $state("");

    let status = $state("not started");
    async function handleSubmit(event: Event) {
        event.preventDefault(); // prevent page reload

        if (!username || !password) {
            alert("Please enter both username and password");
        }
        status = "loading";
        try {
            await userManager.signup(username, password);
            status = "done";
        } catch (error) {
            alert("Failed to create user");
            status = "not started";
            return;
        }
    }
</script>

{#if status == "not started"}
    <div class="container">
        <h3>Create new user</h3>
        <form onsubmit={handleSubmit}>
            <div>
                <label for="username">Username:</label>
                <input
                    type="text"
                    id="username"
                    placeholder="Enter your username"
                    bind:value={username}
                />
            </div>
            <div>
                <label for="password">Password:</label>
                <input
                    type="password"
                    id="password"
                    placeholder="Enter your password"
                    bind:value={password}
                />
            </div>
            <div>
                <button type="submit" disabled={!username || !password}
                    >Create</button
                >
            </div>
        </form>
    </div>
{:else if status == "loading"}
    <div>Loading...</div>
{:else if status == "done"}
    <div>User created successfully</div>
{/if}

<style>
    .container {
        margin: 0;
        position: absolute;
        top: 50%;
        left: 50%;
        -ms-transform: translate(-50%, -50%);
        transform: translate(-50%, -50%);

        padding: 3em;
        background-color: #e8e8e8;
        border-radius: 10px;
    }
    form {
        display: flex;
        flex-direction: column;
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
</style>
