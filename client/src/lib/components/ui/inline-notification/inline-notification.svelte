<script lang="ts">
    import * as Alert from "$lib/components/ui/alert/index.js";
    import type { WithElementRef } from "$lib/utils.js";
    import ErrorFilled from "carbon-icons-svelte/lib/ErrorFilled.svelte";
    import WarningFilled from "carbon-icons-svelte/lib/WarningFilled.svelte";
    import type { HTMLAttributes } from "svelte/elements";

    // Carbon InlineNotification API, low contrast, error and warning kinds, no close button.
    type InlineNotificationProps = Omit<
        WithElementRef<HTMLAttributes<HTMLDivElement>>,
        "title" | "role" | "children"
    > & {
        kind?: "error" | "warning";
        title: string; // no trailing period
        subtitle?: string;
        // Default: alert for an error, status for a warning; "none" renders no role attribute.
        role?: "alert" | "status" | "none";
    };

    let {
        kind = "error",
        title,
        subtitle,
        role,
        ref = $bindable(null),
        ...restProps
    }: InlineNotificationProps = $props();

    const resolvedRole = $derived(
        role ?? (kind === "error" ? "alert" : "status"),
    );
</script>

<Alert.Root
    bind:ref
    variant={kind === "warning" ? "warning" : "destructive"}
    role={resolvedRole === "none" ? undefined : resolvedRole}
    {...restProps}
>
    {#if kind === "warning"}
        <WarningFilled size={20} />
    {:else}
        <ErrorFilled size={20} />
    {/if}
    <Alert.Title>{title}</Alert.Title>
    {#if subtitle}
        <Alert.Description>{subtitle}</Alert.Description>
    {/if}
</Alert.Root>
