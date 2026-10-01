<script lang="ts">
    import { resolve } from "$app/paths";
    import { page } from "$app/state";
    import {
        grantMembership,
        listMemberships,
        listProjects,
        listUsers,
        revokeMembership,
        setActive,
        setPassword,
        type RoleName,
    } from "$lib/admin/api";
    import { ApiError } from "$lib/api/client";
    import * as AlertDialog from "$lib/components/ui/alert-dialog";
    import { Button } from "$lib/components/ui/button";
    import * as Table from "$lib/components/ui/table";
    import type {
        AdminProjectResponse,
        AdminUserResponse,
        MembershipResponse,
    } from "../../../../types/openapi_types";

    const ROLES: { value: RoleName; label: string }[] = [
        { value: "read_only", label: "Read-only" },
        { value: "grader", label: "Grader" },
        { value: "project_admin", label: "Project admin" },
    ];

    const userId = Number(page.params.id);

    let data = $state<{
        user: AdminUserResponse;
        memberships: MembershipResponse[];
        projects: AdminProjectResponse[];
    } | null>(null);
    let notFound = $state(false);
    let error = $state("");
    let grantProject = $state<number | undefined>(undefined);
    let grantRole = $state<RoleName>("read_only");

    const available = $derived.by(() => {
        if (!data) return [];
        const held = new Set(data.memberships.map((m) => m.project_id));
        return data.projects.filter((p) => !held.has(p.id));
    });

    async function load() {
        try {
            const [users, memberships, projects] = await Promise.all([
                listUsers(),
                listMemberships(userId),
                listProjects(),
            ]);
            const user = users.find((u) => u.id === userId);
            if (!user) {
                notFound = true;
                return;
            }
            data = { user, memberships, projects };
        } catch (e) {
            if (e instanceof ApiError && e.status === 404) notFound = true;
            else error = (e as Error).message;
        }
    }
    load();

    async function run(action: () => Promise<unknown>): Promise<boolean> {
        error = "";
        let ok = true;
        try {
            await action();
        } catch (e) {
            error = (e as Error).message;
            ok = false;
        }
        await load();
        return ok;
    }

    async function grant(event: SubmitEvent) {
        event.preventDefault();
        if (grantProject === undefined) return;
        const projectId = grantProject;
        grantProject = undefined;
        await run(() => grantMembership(projectId, userId, grantRole));
    }

    let pending = $state<{ text: string; run: () => Promise<unknown> } | null>(
        null,
    );
    let newPassword = $state("");
    let passwordSet = $state(false);

    function confirmThen(text: string, action: () => Promise<unknown>) {
        pending = { text, run: action };
    }

    async function confirmed() {
        const action = pending?.run;
        pending = null;
        if (action) await run(action);
    }

    async function changePassword(event: SubmitEvent) {
        event.preventDefault();
        passwordSet = await run(() => setPassword(userId, newPassword));
        if (passwordSet) newPassword = "";
    }
</script>

<a class="underline" href={resolve("/admin")}>← Users</a>

{#if error}
    <p class="mt-4 text-red-600">{error}</p>
{/if}

{#if notFound}
    <p class="mt-6">User not found</p>
{:else if data}
    <h2 class="mt-4 mb-6 text-2xl font-bold">
        {data.user.username}
        {#if data.user.is_admin}<span class="text-sm">Admin</span>{/if}
        <span class="text-sm">{data.user.active ? "Active" : "Inactive"}</span>
        {#if !data.user.has_credential}<span class="text-sm">No password</span
            >{/if}
    </h2>

    <h3 class="mb-2 text-lg font-semibold">Memberships</h3>
    {#key data}
        <Table.Root>
            <Table.Header>
                <Table.Row>
                    <Table.Head>Project</Table.Head>
                    <Table.Head>Role</Table.Head>
                    <Table.Head></Table.Head>
                </Table.Row>
            </Table.Header>
            <Table.Body>
                {#each data.memberships as m (m.project_id)}
                    <Table.Row>
                        <Table.Cell>{m.project_name}</Table.Cell>
                        <Table.Cell>
                            <select
                                aria-label={`Role in ${m.project_name}`}
                                value={m.role}
                                onchange={(e) =>
                                    run(() =>
                                        grantMembership(
                                            m.project_id,
                                            userId,
                                            e.currentTarget.value as RoleName,
                                        ),
                                    )}
                            >
                                {#each ROLES as role (role.value)}
                                    <option value={role.value}
                                        >{role.label}</option
                                    >
                                {/each}
                            </select>
                        </Table.Cell>
                        <Table.Cell>
                            <Button
                                variant="outline"
                                size="sm"
                                onclick={() =>
                                    confirmThen(
                                        `Remove ${data?.user.username} from ${m.project_name}?`,
                                        () =>
                                            revokeMembership(
                                                m.project_id,
                                                userId,
                                            ),
                                    )}>Revoke</Button
                            >
                        </Table.Cell>
                    </Table.Row>
                {/each}
            </Table.Body>
        </Table.Root>
    {/key}

    {#if available.length > 0}
        <form onsubmit={grant} class="mt-4 flex items-end gap-2">
            <div class="flex flex-col">
                <label for="grant-project">Project</label>
                <select id="grant-project" bind:value={grantProject} required>
                    {#each available as p (p.id)}
                        <option value={p.id}>{p.name}</option>
                    {/each}
                </select>
            </div>
            <div class="flex flex-col">
                <label for="grant-role">Role</label>
                <select id="grant-role" bind:value={grantRole}>
                    {#each ROLES as role (role.value)}
                        <option value={role.value}>{role.label}</option>
                    {/each}
                </select>
            </div>
            <Button type="submit">Grant</Button>
        </form>
    {/if}

    <h3 class="mt-8 mb-2 text-lg font-semibold">Account</h3>
    {#if data.user.active}
        <Button
            variant="destructive"
            onclick={() =>
                confirmThen(
                    `Deactivate ${data?.user.username}? They are signed out at their next token refresh.`,
                    () => setActive(userId, false),
                )}>Deactivate</Button
        >
    {:else}
        <Button onclick={() => run(() => setActive(userId, true))}
            >Reactivate</Button
        >
    {/if}

    <form onsubmit={changePassword} class="mt-4 flex items-end gap-2">
        <label class="flex flex-col">
            New password
            <input
                class="rounded border px-2 py-1"
                type="password"
                autocomplete="new-password"
                bind:value={newPassword}
                aria-describedby="password-hint"
                required
            />
        </label>
        <Button type="submit">Set password</Button>
        {#if passwordSet}<span>Password set.</span>{/if}
    </form>
    <p id="password-hint" class="text-gray-600">
        At least 15 characters. Must not contain the username or "eyened".
    </p>

    <AlertDialog.Root
        open={pending !== null}
        onOpenChange={(open) => {
            if (!open) pending = null;
        }}
    >
        <AlertDialog.Content>
            <AlertDialog.Title>Are you sure?</AlertDialog.Title>
            <AlertDialog.Description>{pending?.text}</AlertDialog.Description>
            <div class="flex justify-end gap-2">
                <AlertDialog.Cancel>Cancel</AlertDialog.Cancel>
                <AlertDialog.Action onclick={confirmed}
                    >Confirm</AlertDialog.Action
                >
            </div>
        </AlertDialog.Content>
    </AlertDialog.Root>
{/if}
