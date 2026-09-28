<script lang="ts">
    import { resolve } from "$app/paths";
    import { page } from "$app/state";
    import {
        grantMembership,
        listMemberships,
        listProjects,
        listUsers,
        type RoleName,
    } from "$lib/admin/api";
    import { ApiError } from "$lib/api/client";
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
                        <Table.Cell></Table.Cell>
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
{/if}
