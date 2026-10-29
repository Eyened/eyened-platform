<script lang="ts">
    import { goto } from "$app/navigation";
    import { resolve } from "$app/paths";
    import { accountStatus, PASSWORD_HINT } from "$lib/admin/accountStatus";
    import { createUser, listUsers } from "$lib/admin/api";
    import { Button } from "$lib/components/ui/button/index.js";
    import * as Empty from "$lib/components/ui/empty/index.js";
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import { Modal } from "$lib/components/ui/modal/index.js";
    import { StatusIndicator } from "$lib/components/ui/status-indicator/index.js";
    import * as Table from "$lib/components/ui/table/index.js";
    import { Tag } from "$lib/components/ui/tag/index.js";
    import {
        PasswordInput,
        TextInput,
    } from "$lib/components/ui/text-input/index.js";
    import Add from "carbon-icons-svelte/lib/Add.svelte";
    import type { AdminUserResponse } from "../../types/openapi_types";

    const PAGE_SIZES = [10, 20, 50, 100];
    const HEADERS = ["Username", "Status", "Password", "Employee ID"];
    const headingId = "users-heading";
    const hintId = "create-password-hint";

    const loading = listUsers();

    let search = $state("");
    let page = $state(1);
    let pageSize = $state(20);

    let createOpen = $state(false);
    let username = $state("");
    let password = $state("");
    let missing = $state(false);

    // Search and paging run on the client: the endpoint returns every user.
    function matching(users: AdminUserResponse[]): AdminUserResponse[] {
        const query = search.trim().toLowerCase();
        return query
            ? users.filter((u) => u.username.toLowerCase().includes(query))
            : users;
    }

    function openCreate() {
        username = "";
        password = "";
        missing = false;
        createOpen = true;
    }

    function create() {
        if (!username.trim() || !password) {
            missing = true;
            return false;
        }
        return createUser(username, password).then((user) =>
            goto(resolve("/admin/users/[id]", { id: String(user.id) })),
        );
    }
</script>

<h1 id={headingId} tabindex="-1" class="mb-6 text-heading-04 text-text-primary">
    Users
</h1>

{#await loading}
    <Table.Skeleton headers={HEADERS} aria-labelledby={headingId} />
{:then users}
    {@const visible = matching(users)}
    <Table.Toolbar>
        <Table.ToolbarSearch
            labelText="Search users"
            placeholder="Search users"
            bind:value={
                () => search,
                (v) => {
                    search = v;
                    page = 1;
                }
            }
        />
        <Button size="lg" class="ms-auto" onclick={openCreate}>
            Create user <Add />
        </Button>
    </Table.Toolbar>

    {#if visible.length === 0}
        <Empty.Root>
            <Empty.Header>
                {#if search.trim()}
                    <Empty.Title>No users match “{search.trim()}”</Empty.Title>
                    <Empty.Description>
                        Try a different search term.
                    </Empty.Description>
                {:else}
                    <Empty.Title>No users yet</Empty.Title>
                {/if}
            </Empty.Header>
        </Empty.Root>
    {:else}
        <Table.Root aria-labelledby={headingId}>
            <Table.Header>
                <Table.Row>
                    {#each HEADERS as header (header)}
                        <Table.Head>{header}</Table.Head>
                    {/each}
                </Table.Row>
            </Table.Header>
            <Table.Body>
                {#each visible.slice((page - 1) * pageSize, page * pageSize) as user (user.id)}
                    {@const status = accountStatus(user)}
                    <Table.Row>
                        <Table.Cell>
                            <span class="flex items-center gap-2">
                                <a
                                    href={resolve("/admin/users/[id]", {
                                        id: String(user.id),
                                    })}
                                    class="text-link-primary hover:text-link-primary-hover hover:underline"
                                >
                                    {user.username}
                                </a>
                                {#if user.is_admin}<Tag>Admin</Tag>{/if}
                            </span>
                        </Table.Cell>
                        <Table.Cell>
                            <StatusIndicator
                                icon={status.icon}
                                iconClass={status.iconClass}
                                label={status.label}
                            />
                        </Table.Cell>
                        <Table.Cell>
                            {user.has_credential ? "" : "No password"}
                        </Table.Cell>
                        <Table.Cell
                            >{user.employee_identifier ?? "—"}</Table.Cell
                        >
                    </Table.Row>
                {/each}
            </Table.Body>
        </Table.Root>
        <Table.Pagination
            {page}
            {pageSize}
            pageSizes={PAGE_SIZES}
            totalItems={visible.length}
            onchange={(p) => {
                page = p.page;
                pageSize = p.pageSize;
            }}
        />
    {/if}
{:catch error}
    <InlineNotification
        title="Users could not be loaded"
        subtitle={error instanceof Error ? error.message : String(error)}
    />
{/await}

<Modal
    bind:open={createOpen}
    modalHeading="Create user"
    primaryButtonText="Create user"
    primaryButtonLoadingDescription="Creating…"
    successDescription="Created"
    errorTitle="User could not be created"
    onsubmit={create}
>
    <div class="flex flex-col gap-6">
        <TextInput
            labelText="Username"
            bind:value={username}
            autocomplete="off"
            invalidText={missing && !username.trim()
                ? "Enter a username"
                : undefined}
        />
        <!-- Helper text 4 px below the field; the error replaces it -->
        <div class="flex flex-col gap-1">
            <PasswordInput
                labelText="Password"
                bind:value={password}
                autocomplete="new-password"
                aria-describedby={missing && !password ? undefined : hintId}
                invalidText={missing && !password
                    ? "Enter a password"
                    : undefined}
            />
            {#if !(missing && !password)}
                <p id={hintId} class="text-helper-text-01 text-text-helper">
                    {PASSWORD_HINT}
                </p>
            {/if}
        </div>
    </div>
</Modal>
