<script lang="ts">
    import Main from "$lib/components/Main.svelte";
    import { fetchApi } from "$lib/api/client";
    import { onMount } from "svelte";

    type AdminUser = {
        id: number;
        username: string;
        role: number | null;
        is_human: boolean;
    };

    type TaskRow = {
        id: number;
        name: string;
        description?: string | null;
        num_tasks?: number;
    };

    type SubtaskRow = {
        id: number;
        task_id: number;
        task_state: string;
        creator_id: number | null;
        comments?: string | null;
    };

    type CVIRow = {
        id: string | number;
        status?: string | null;
        subtask_id?: number | null;
        subtask_assignee_user_id?: number | null;
        subtask_assignee_username?: string | null;
        changes?: number | null;
    };

    type CVISubtaskOption = {
        id: number;
        task_state: string;
        creator_id: number | null;
    };

    let loading = $state(true);
    let error = $state("");
    let info = $state("");
    let accessDenied = $state(false);

    let activeTab = $state<"users" | "tasks" | "cvi">("users");

    let users = $state<AdminUser[]>([]);
    let tasks = $state<TaskRow[]>([]);
    let selectedTaskId = $state<number | null>(null);
    let subtasks = $state<SubtaskRow[]>([]);
    let cviRows = $state<CVIRow[]>([]);
    let cviTotal = $state(0);
    let cviSearch = $state("");
    let cviSubtaskOptions = $state<CVISubtaskOption[]>([]);
    let cviPage = $state(1);
    let cviLimit = $state(100);

    let newUsername = $state("");
    let newPassword = $state("");
    let newRole = $state("1");

    function userDisplayName(userId: number | null | undefined): string {
        if (userId == null) return "Unassigned";
        const found = users.find((u) => u.id === userId);
        return found ? found.username : `User ${userId}`;
    }

    async function loadUsers() {
        const res = await fetchApi("/management/users");
        if (res.status === 403) {
            accessDenied = true;
            return;
        }
        if (!res.ok) {
            throw new Error(`Failed to load users (${res.status})`);
        }
        users = (await res.json()) as AdminUser[];
    }

    async function loadTasks() {
        const res = await fetchApi("/task");
        if (!res.ok) {
            throw new Error(`Failed to load tasks (${res.status})`);
        }
        const data = (await res.json()) as TaskRow[];
        tasks = data;

        if (tasks.length > 0 && selectedTaskId == null) {
            selectedTaskId = tasks[0].id;
            await loadSubtasks();
        }
    }

    async function loadSubtasks() {
        subtasks = [];
        if (selectedTaskId == null) return;

        const res = await fetchApi(`/task/${selectedTaskId}/subtasks`, {
            query: { with_images: false, limit: 200, page: 0 },
        });
        if (!res.ok) {
            throw new Error(`Failed to load subtasks (${res.status})`);
        }
        const payload = (await res.json()) as { subtasks: SubtaskRow[] };
        subtasks = payload.subtasks ?? [];
    }

    const cviTotalPages = $derived(Math.max(1, Math.ceil(cviTotal / cviLimit)));
    const cviOffset = $derived((cviPage - 1) * cviLimit);
    const cviFrom = $derived(cviTotal === 0 ? 0 : cviOffset + 1);
    const cviTo = $derived(Math.min(cviOffset + cviRows.length, cviTotal));

    async function loadCviRows() {
        const res = await fetchApi("/management/cvi/records", {
            query: {
                limit: cviLimit,
                offset: cviOffset,
                search: cviSearch.trim() || undefined,
            },
        });
        if (!res.ok) {
            throw new Error(`Failed to load CVI assignments (${res.status})`);
        }

        const payload = (await res.json()) as { rows: CVIRow[]; total: number };
        cviRows = payload.rows ?? [];
        cviTotal = payload.total ?? 0;

        if (cviPage > cviTotalPages) {
            cviPage = cviTotalPages;
            await loadCviRows();
        }
    }

    async function searchCviRows() {
        cviPage = 1;
        await loadCviRows();
    }

    async function prevCviPage() {
        if (cviPage <= 1) return;
        cviPage -= 1;
        await loadCviRows();
    }

    async function nextCviPage() {
        if (cviPage >= cviTotalPages) return;
        cviPage += 1;
        await loadCviRows();
    }

    async function loadCviSubtaskOptions() {
        cviSubtaskOptions = [];
        const cviTask = tasks.find((t) => t.name.toLowerCase().includes("cvi"));
        if (!cviTask) {
            return;
        }

        const res = await fetchApi(`/task/${cviTask.id}/subtasks`, {
            query: { with_images: false, limit: 2000, page: 0 },
        });
        if (!res.ok) {
            throw new Error(`Failed to load CVI subtasks (${res.status})`);
        }
        const payload = (await res.json()) as { subtasks: SubtaskRow[] };
        cviSubtaskOptions = (payload.subtasks ?? []).map((st) => ({
            id: st.id,
            task_state: st.task_state,
            creator_id: st.creator_id,
        }));
    }

    async function saveUserRole(user: AdminUser, roleValue: string) {
        error = "";
        info = "";
        const role = roleValue.trim() === "" ? null : Number(roleValue);
        const res = await fetchApi(`/management/users/${user.id}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ role }),
        });
        if (!res.ok) {
            throw new Error(`Failed to update user (${res.status})`);
        }
        info = `Updated role for ${user.username}`;
        await loadUsers();
    }

    async function createManagedUser() {
        error = "";
        info = "";
        if (!newUsername.trim() || !newPassword) {
            error = "Username and password are required.";
            return;
        }

        const role = newRole.trim() === "" ? null : Number(newRole);
        const res = await fetchApi("/management/users", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                username: newUsername.trim(),
                password: newPassword,
                role,
            }),
        });

        if (!res.ok) {
            throw new Error(`Failed to create user (${res.status})`);
        }

        newUsername = "";
        newPassword = "";
        info = "User created";
        await loadUsers();
    }

    async function deleteManagedUser(user: AdminUser) {
        if (!confirm(`Delete user ${user.username}?`)) return;

        error = "";
        info = "";
        const res = await fetchApi(`/management/users/${user.id}`, {
            method: "DELETE",
        });
        if (!res.ok) {
            throw new Error(`Failed to delete user (${res.status})`);
        }

        info = `Deleted ${user.username}`;
        await loadUsers();
    }

    async function assignSubtask(subtaskId: number, userId: string) {
        error = "";
        info = "";
        const creator_id = userId ? Number(userId) : null;

        const res = await fetchApi(`/subtasks/${subtaskId}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ creator_id }),
        });
        if (!res.ok) {
            throw new Error(`Failed to assign subtask (${res.status})`);
        }

        info = `Updated assignee for subtask ${subtaskId}`;
        await loadSubtasks();
    }

    async function assignCviRow(rowId: string | number, subtaskId: string) {
        error = "";
        info = "";

        const subtask_id = subtaskId ? Number(subtaskId) : null;
        const res = await fetchApi(`/management/cvi/records/${rowId}/assign`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ subtask_id }),
        });
        if (!res.ok) {
            throw new Error(`Failed to assign CVI row (${res.status})`);
        }

        info = `Updated SubTaskID for CVI row ${rowId}`;
        await loadCviRows();
        await loadTasks();
        await loadCviSubtaskOptions();
    }

    async function initPage() {
        loading = true;
        error = "";
        info = "";
        try {
            await loadUsers();
            if (accessDenied) return;
            await loadTasks();
            await Promise.all([loadCviRows(), loadCviSubtaskOptions()]);
        } catch (err) {
            error = err instanceof Error ? err.message : "Failed to load management data";
        } finally {
            loading = false;
        }
    }

    onMount(async () => {
        await initPage();
    });
</script>

<svelte:head>
    <title>Management</title>
</svelte:head>

<Main>
    {#snippet children()}
        <div class="management-page">
            <h1>Management</h1>

            {#if loading}
                <p>Loading management data...</p>
            {:else if accessDenied}
                <p class="error">Admin access required.</p>
            {:else}
                {#if error}
                    <p class="error">{error}</p>
                {/if}
                {#if info}
                    <p class="message">{info}</p>
                {/if}

                <div class="tabs">
                    <button class:active={activeTab === "users"} onclick={() => (activeTab = "users")}>Users</button>
                    <button class:active={activeTab === "tasks"} onclick={() => (activeTab = "tasks")}>Tasks</button>
                    <button class:active={activeTab === "cvi"} onclick={() => (activeTab = "cvi")}>CVI</button>
                </div>

                {#if activeTab === "users"}
                    <section class="panel">
                        <h2>Users</h2>
                        <div class="new-user-grid">
                            <input placeholder="username" bind:value={newUsername} />
                            <input placeholder="password" type="password" bind:value={newPassword} />
                            <input placeholder="role (e.g. 1)" bind:value={newRole} />
                            <button onclick={createManagedUser}>Create User</button>
                        </div>

                        <table>
                            <thead>
                                <tr>
                                    <th>ID</th>
                                    <th>Username</th>
                                    <th>Role</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {#each users as user (user.id)}
                                    <tr>
                                        <td>{user.id}</td>
                                        <td>{user.username}</td>
                                        <td>
                                            <input
                                                value={user.role ?? ""}
                                                onblur={(e) => saveUserRole(user, (e.currentTarget as HTMLInputElement).value)}
                                            />
                                        </td>
                                        <td>
                                            <button class="danger" onclick={() => deleteManagedUser(user)}>Delete</button>
                                        </td>
                                    </tr>
                                {/each}
                            </tbody>
                        </table>
                    </section>
                {/if}

                {#if activeTab === "tasks"}
                    <section class="panel">
                        <h2>Tasks</h2>
                        <div class="task-controls">
                            <label for="taskSelect">Task:</label>
                            <select
                                id="taskSelect"
                                bind:value={selectedTaskId}
                                onchange={loadSubtasks}
                            >
                                {#each tasks as task (task.id)}
                                    <option value={task.id}>{task.name} ({task.num_tasks ?? 0})</option>
                                {/each}
                            </select>
                        </div>

                        <table>
                            <thead>
                                <tr>
                                    <th>Subtask ID</th>
                                    <th>Status</th>
                                    <th>Assignee</th>
                                    <th>Comments</th>
                                </tr>
                            </thead>
                            <tbody>
                                {#each subtasks as st (st.id)}
                                    <tr>
                                        <td>{st.id}</td>
                                        <td>{st.task_state}</td>
                                        <td>
                                            <select
                                                value={st.creator_id ?? ""}
                                                onchange={(e) =>
                                                    assignSubtask(
                                                        st.id,
                                                        (e.currentTarget as HTMLSelectElement).value,
                                                    )}
                                            >
                                                <option value="">Unassigned</option>
                                                {#each users as user (user.id)}
                                                    <option value={user.id}>{user.username}</option>
                                                {/each}
                                            </select>
                                        </td>
                                        <td>{st.comments ?? ""}</td>
                                    </tr>
                                {:else}
                                    <tr>
                                        <td colspan="4">No subtasks in this task.</td>
                                    </tr>
                                {/each}
                            </tbody>
                        </table>
                    </section>
                {/if}

                {#if activeTab === "cvi"}
                    <section class="panel">
                        <h2>CVI Assignment</h2>
                        <div class="task-controls">
                            <input placeholder="Search" bind:value={cviSearch} />
                            <button onclick={searchCviRows}>Search</button>
                            <span>Total: {cviTotal}</span>
                            <span>Showing: {cviFrom}-{cviTo}</span>
                            <span>Page {cviPage} / {cviTotalPages}</span>
                            <button onclick={prevCviPage} disabled={cviPage <= 1}>Prev</button>
                            <button onclick={nextCviPage} disabled={cviPage >= cviTotalPages}>Next</button>
                        </div>

                        <table>
                            <thead>
                                <tr>
                                    <th>Row ID</th>
                                    <th>Status</th>
                                    <th>Changes</th>
                                    <th>SubTaskID</th>
                                    <th>SubTask Assignee</th>
                                </tr>
                            </thead>
                            <tbody>
                                {#each cviRows as row (row.id)}
                                    <tr>
                                        <td>{row.id}</td>
                                        <td>{row.status ?? ""}</td>
                                        <td>{row.changes ?? 0}</td>
                                        <td>
                                            <select
                                                value={row.subtask_id ?? ""}
                                                onchange={(e) =>
                                                    assignCviRow(
                                                        row.id,
                                                        (e.currentTarget as HTMLSelectElement).value,
                                                    )}
                                            >
                                                <option value="">Unassigned</option>
                                                {#each cviSubtaskOptions as subtask (subtask.id)}
                                                    <option value={subtask.id}>
                                                        {subtask.id} ({subtask.task_state})
                                                    </option>
                                                {/each}
                                            </select>
                                        </td>
                                        <td>
                                            {#if row.subtask_assignee_user_id}
                                                {row.subtask_assignee_username ?? `User ${row.subtask_assignee_user_id}`}
                                                <small>ID: {row.subtask_assignee_user_id}</small>
                                            {:else}
                                                -
                                            {/if}
                                        </td>
                                    </tr>
                                {/each}
                            </tbody>
                        </table>
                    </section>
                {/if}
            {/if}
        </div>
    {/snippet}
</Main>

<style>
    .management-page {
        width: 100%;
        max-width: 1400px;
        margin: 0 auto;
        padding: 20px;
        display: grid;
        gap: 12px;
    }

    .tabs {
        display: flex;
        gap: 8px;
    }

    .tabs button {
        padding: 8px 12px;
        border: 1px solid #ccc;
        border-radius: 8px;
        background: #f3f4f6;
    }

    .tabs button.active {
        background: #111827;
        border-color: #111827;
        color: #fff;
    }

    .panel {
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 12px;
        display: grid;
        gap: 10px;
        background: #fff;
    }

    .new-user-grid,
    .task-controls {
        display: flex;
        gap: 8px;
        align-items: center;
        flex-wrap: wrap;
    }

    table {
        width: 100%;
        border-collapse: collapse;
        font-size: 13px;
    }

    th,
    td {
        border: 1px solid #e5e7eb;
        padding: 6px 8px;
        text-align: left;
        vertical-align: middle;
    }

    input,
    select,
    button {
        padding: 6px 8px;
        border: 1px solid #cfcfcf;
        border-radius: 6px;
        font-size: 13px;
    }

    button {
        background: #f9fafb;
    }

    button.danger {
        border-color: #fecaca;
        color: #991b1b;
        background: #fef2f2;
    }

    .error {
        color: #b42318;
    }

    .message {
        color: #0f766e;
    }

    small {
        display: block;
        color: #555;
    }
</style>
