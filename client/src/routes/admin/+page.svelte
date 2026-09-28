<script lang="ts">
    import { goto } from "$app/navigation";
    import { resolve } from "$app/paths";
    import { createUser, listUsers } from "$lib/admin/api";
    import { Button } from "$lib/components/ui/button";
    import * as Table from "$lib/components/ui/table";
    import type { AdminUserResponse } from "../../types/openapi_types";

    let users = $state<AdminUserResponse[]>([]);
    let error = $state("");
    let username = $state("");
    let password = $state("");

    async function load() {
        try {
            users = await listUsers();
        } catch (e) {
            error = (e as Error).message;
        }
    }
    load();

    async function create(event: SubmitEvent) {
        event.preventDefault();
        error = "";
        try {
            const user = await createUser(username, password);
            await goto(resolve("/admin/users/[id]", { id: String(user.id) }));
        } catch (e) {
            error = (e as Error).message;
        }
    }
</script>

<h2 class="mb-6 text-2xl font-bold">Users</h2>

{#if error}
    <p class="mb-4 text-red-600">{error}</p>
{/if}

<form onsubmit={create} class="mb-2 flex items-end gap-2">
    <label class="flex flex-col">
        Username
        <input
            class="rounded border px-2 py-1"
            bind:value={username}
            required
        />
    </label>
    <label class="flex flex-col">
        Password
        <input
            class="rounded border px-2 py-1"
            type="password"
            bind:value={password}
            aria-describedby="password-hint"
            required
        />
    </label>
    <Button type="submit">Create user</Button>
</form>
<p id="password-hint" class="mb-6 text-gray-600">
    At least 15 characters. Must not contain the username or "eyened".
</p>

<Table.Root>
    <Table.Header>
        <Table.Row>
            <Table.Head>Username</Table.Head>
            <Table.Head>Admin</Table.Head>
            <Table.Head>Status</Table.Head>
            <Table.Head>Password</Table.Head>
            <Table.Head>Employee ID</Table.Head>
        </Table.Row>
    </Table.Header>
    <Table.Body>
        {#each users as user (user.id)}
            <Table.Row class={user.active ? "" : "opacity-50"}>
                <Table.Cell>
                    <a
                        class="underline"
                        href={resolve("/admin/users/[id]", {
                            id: String(user.id),
                        })}>{user.username}</a
                    >
                </Table.Cell>
                <Table.Cell>{user.is_admin ? "Admin" : ""}</Table.Cell>
                <Table.Cell>{user.active ? "Active" : "Inactive"}</Table.Cell>
                <Table.Cell
                    >{user.has_credential ? "" : "No password"}</Table.Cell
                >
                <Table.Cell>{user.employee_identifier ?? ""}</Table.Cell>
            </Table.Row>
        {/each}
    </Table.Body>
</Table.Root>
