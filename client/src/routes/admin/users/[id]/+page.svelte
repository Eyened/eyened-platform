<script lang="ts">
    import { resolve } from "$app/paths";
    import { page } from "$app/state";
    import { accountStatus, PASSWORD_HINT } from "$lib/admin/accountStatus";
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
    import * as Breadcrumb from "$lib/components/ui/breadcrumb/index.js";
    import { Button } from "$lib/components/ui/button/index.js";
    import * as Empty from "$lib/components/ui/empty/index.js";
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import { Modal } from "$lib/components/ui/modal/index.js";
    import {
        SelectInput,
        SelectItem,
    } from "$lib/components/ui/select-input/index.js";
    import { StatusIndicator } from "$lib/components/ui/status-indicator/index.js";
    import * as Table from "$lib/components/ui/table/index.js";
    import { Tag } from "$lib/components/ui/tag/index.js";
    import { PasswordInput } from "$lib/components/ui/text-input/index.js";
    import { cn } from "$lib/utils.js";
    import Add from "carbon-icons-svelte/lib/Add.svelte";
    import Subtract from "carbon-icons-svelte/lib/Subtract.svelte";
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
    const HEADERS = ["Project", "Role", ""];
    const headingId = "user-heading";
    const membershipsId = "memberships-heading";
    const hintId = "set-password-hint";

    const userId = Number(page.params.id);

    let data = $state<{
        user: AdminUserResponse;
        memberships: MembershipResponse[];
        projects: AdminProjectResponse[];
    } | null>(null);
    let notFound = $state(false);
    let loadError = $state("");
    let notice = $state<{ title: string; subtitle: string } | null>(null);

    const available = $derived.by(() => {
        if (!data) return [];
        const held = new Set(data.memberships.map((m) => m.project_id));
        return data.projects.filter((p) => !held.has(p.id));
    });

    function roleLabel(role: RoleName): string {
        return ROLES.find((r) => r.value === role)?.label ?? role;
    }

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
            const message = (e as Error).message;
            if (e instanceof ApiError && e.status === 404) notFound = true;
            else if (data)
                notice = {
                    title: "User could not be reloaded",
                    subtitle: message,
                };
            else loadError = message;
        }
    }
    load();

    // An action without a modal: a failure shows above the memberships.
    async function run(title: string, action: () => Promise<unknown>) {
        notice = null;
        try {
            await action();
        } catch (e) {
            notice = { title, subtitle: (e as Error).message };
        }
        await load();
    }

    // A modal's write: a rejection stays in the modal; success reloads the page.
    async function save(write: Promise<unknown>) {
        await write;
        notice = null;
        await load();
    }

    // The trigger is gone after a remove or a deactivate, so focus goes to the heading.
    function focusHeadingIf(gone: () => boolean) {
        return (event: Event) => {
            if (gone()) {
                event.preventDefault();
                document.getElementById(headingId)?.focus();
            }
        };
    }

    let removing = $state<MembershipResponse | null>(null);
    let removeOpen = $state(false);

    let addOpen = $state(false);
    let addProject = $state("");
    let addRole = $state<string>("read_only");

    let deactivateOpen = $state(false);

    let passwordOpen = $state(false);
    let newPassword = $state("");
    let passwordMissing = $state(false);

    function openRemove(m: MembershipResponse) {
        removing = m;
        removeOpen = true;
    }

    function openAdd() {
        if (available.length === 0) return;
        addProject = String(available[0].id);
        addRole = "read_only";
        addOpen = true;
    }

    function openPassword() {
        newPassword = "";
        passwordMissing = false;
        passwordOpen = true;
    }

    function submitPassword() {
        if (!newPassword) {
            passwordMissing = true;
            return false;
        }
        return save(setPassword(userId, newPassword));
    }
</script>

<Breadcrumb.Root>
    <Breadcrumb.List>
        <Breadcrumb.Item>
            <Breadcrumb.Link href={resolve("/admin")}>Users</Breadcrumb.Link>
        </Breadcrumb.Item>
    </Breadcrumb.List>
</Breadcrumb.Root>

{#if loadError}
    <InlineNotification
        class="mt-6"
        title="User could not be loaded"
        subtitle={loadError}
    />
{:else if notFound}
    <Empty.Root class="mt-6">
        <Empty.Header>
            <Empty.Title>User not found</Empty.Title>
        </Empty.Header>
    </Empty.Root>
{:else if !data}
    <span class={cn(Table.skeleton, "mt-2 mb-6 h-6 w-40")}></span>
    <Table.Skeleton headers={HEADERS} />
{:else}
    {@const user = data.user}
    {@const status = accountStatus(user)}
    <div class="mt-2 mb-10">
        <div class="flex flex-wrap items-center gap-4">
            <!-- tabindex=-1: focus lands here when a removed row's, Deactivate's or Reactivate's button is gone -->
            <h1
                id={headingId}
                tabindex="-1"
                class="text-heading-04 text-text-primary"
            >
                {user.username}
            </h1>
            {#if user.is_admin}<Tag>Admin</Tag>{/if}
            <StatusIndicator
                icon={status.icon}
                iconClass={status.iconClass}
                label={status.label}
            />
        </div>
        {#if !user.has_credential}
            <p class="mt-2 text-body-01 text-text-secondary">No password</p>
        {/if}
    </div>

    {#if notice}
        <InlineNotification
            class="mb-4"
            title={notice.title}
            subtitle={notice.subtitle}
        />
    {/if}

    <!-- Carbon data table header: layer background, 16 / 24 px block padding, heading-03 -->
    <div class="bg-layer-01 px-4 pt-4 pb-6">
        <h2 id={membershipsId} class="text-heading-03 text-text-primary">
            Memberships
        </h2>
    </div>
    <Table.Toolbar>
        <Button
            size="lg"
            class="ms-auto"
            aria-disabled={available.length === 0 || undefined}
            onclick={openAdd}
        >
            Add to project <Add />
        </Button>
    </Table.Toolbar>
    {#if data.memberships.length === 0}
        <Empty.Root>
            <Empty.Header>
                <Empty.Title>No memberships</Empty.Title>
                <Empty.Description>
                    Add {user.username} to a project to give them access.
                </Empty.Description>
            </Empty.Header>
        </Empty.Root>
    {:else}
        <Table.Root aria-labelledby={membershipsId}>
            <Table.Header>
                <Table.Row>
                    <Table.Head>Project</Table.Head>
                    <Table.Head>Role</Table.Head>
                    <Table.Head><span class="sr-only">Actions</span></Table.Head
                    >
                </Table.Row>
            </Table.Header>
            <Table.Body>
                {#each data.memberships as m (m.project_id)}
                    <Table.Row>
                        <Table.Cell>{m.project_name}</Table.Cell>
                        <Table.Cell class="py-0">
                            <SelectInput
                                inline
                                hideLabel
                                labelText="Role in {m.project_name}"
                                value={m.role}
                                onchange={(e) => {
                                    const role = e.currentTarget
                                        .value as RoleName;
                                    run("Role could not be changed", () =>
                                        grantMembership(
                                            m.project_id,
                                            userId,
                                            role,
                                        ),
                                    );
                                }}
                            >
                                {#each ROLES as role (role.value)}
                                    <SelectItem
                                        value={role.value}
                                        text={role.label}
                                    />
                                {/each}
                            </SelectInput>
                        </Table.Cell>
                        <!-- Carbon inline row action: ghost button in a trailing column. -->
                        <Table.Cell class="text-end whitespace-nowrap">
                            <Button
                                variant="ghost"
                                aria-label="Remove from {m.project_name}"
                                onclick={() => openRemove(m)}
                            >
                                Remove <Subtract />
                            </Button>
                        </Table.Cell>
                    </Table.Row>
                {/each}
            </Table.Body>
        </Table.Root>
    {/if}

    <h2 class="mt-10 mb-4 text-heading-compact-02 text-text-primary">
        Account
    </h2>
    <div class="flex flex-wrap gap-4">
        {#if user.active}
            <Button
                variant="destructive"
                onclick={() => (deactivateOpen = true)}
            >
                Deactivate
            </Button>
        {:else}
            <Button
                variant="secondary"
                onclick={() =>
                    run("User could not be reactivated", () =>
                        setActive(userId, true),
                    ).then(() => {
                        if (data?.user.active)
                            document.getElementById(headingId)?.focus();
                    })}
            >
                Reactivate
            </Button>
        {/if}
        <Button variant="secondary" onclick={openPassword}>Set password</Button>
    </div>

    <Modal
        bind:open={removeOpen}
        danger
        size="xs"
        modalHeading={removing
            ? `Remove ${user.username} from ${removing.project_name}?`
            : ""}
        primaryButtonText="Remove"
        primaryButtonLoadingDescription="Removing…"
        successDescription="Removed"
        errorTitle="Membership could not be removed"
        onsubmit={() =>
            removing
                ? save(revokeMembership(removing.project_id, userId))
                : false}
        onCloseAutoFocus={focusHeadingIf(
            () =>
                removing !== null &&
                !data?.memberships.some(
                    (m) => m.project_id === removing?.project_id,
                ),
        )}
    >
        {#if removing}
            <p>
                They lose their {roleLabel(removing.role)} role in {removing.project_name}.
            </p>
        {/if}
    </Modal>

    <Modal
        bind:open={addOpen}
        modalHeading="Add to project"
        modalLabel={user.username}
        primaryButtonText="Add"
        primaryButtonLoadingDescription="Adding…"
        successDescription="Added"
        errorTitle="Membership could not be added"
        onsubmit={() =>
            save(
                grantMembership(
                    Number(addProject),
                    userId,
                    addRole as RoleName,
                ),
            )}
    >
        <div class="flex flex-col gap-6">
            <SelectInput labelText="Project" bind:value={addProject}>
                {#each available as p (p.id)}
                    <SelectItem value={String(p.id)} text={p.name} />
                {/each}
            </SelectInput>
            <SelectInput labelText="Role" bind:value={addRole}>
                {#each ROLES as role (role.value)}
                    <SelectItem value={role.value} text={role.label} />
                {/each}
            </SelectInput>
        </div>
    </Modal>

    <Modal
        bind:open={deactivateOpen}
        danger
        size="xs"
        modalHeading="Deactivate {user.username}?"
        primaryButtonText="Deactivate"
        primaryButtonLoadingDescription="Deactivating…"
        successDescription="Deactivated"
        errorTitle="User could not be deactivated"
        onsubmit={() => save(setActive(userId, false))}
        onCloseAutoFocus={focusHeadingIf(() => data?.user.active === false)}
    >
        <p>They are signed out at their next token refresh.</p>
    </Modal>

    <Modal
        bind:open={passwordOpen}
        modalHeading="Set password"
        modalLabel={user.username}
        primaryButtonText="Set password"
        primaryButtonLoadingDescription="Saving…"
        successDescription="Password set"
        errorTitle="Password could not be set"
        onsubmit={submitPassword}
    >
        <!-- Helper text 4 px below the field; the error replaces it -->
        <div class="flex flex-col gap-1">
            <PasswordInput
                labelText="New password"
                bind:value={newPassword}
                autocomplete="new-password"
                aria-describedby={passwordMissing && !newPassword
                    ? undefined
                    : hintId}
                invalidText={passwordMissing && !newPassword
                    ? "Enter a password"
                    : undefined}
            />
            {#if !(passwordMissing && !newPassword)}
                <p id={hintId} class="text-helper-text-01 text-text-helper">
                    {PASSWORD_HINT}
                </p>
            {/if}
        </div>
    </Modal>
{/if}
