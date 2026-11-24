<script lang="ts">
    import * as Alert from "$lib/components/ui/alert/index.js";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import type { WithElementRef } from "$lib/utils.js";
    import CheckmarkFilled from "carbon-icons-svelte/lib/CheckmarkFilled.svelte";
    import Close from "carbon-icons-svelte/lib/Close.svelte";
    import ErrorFilled from "carbon-icons-svelte/lib/ErrorFilled.svelte";
    import WarningFilled from "carbon-icons-svelte/lib/WarningFilled.svelte";
    import type { HTMLAttributes } from "svelte/elements";

    // Carbon InlineNotification API: error, warning and success kinds, low contrast unless highContrast, an optional close button.
    type InlineNotificationProps = Omit<
        WithElementRef<HTMLAttributes<HTMLDivElement>>,
        "title" | "role" | "children"
    > & {
        kind?: "error" | "warning" | "success";
        title: string; // no trailing period
        subtitle?: string;
        // Default: alert for an error, status otherwise; "none" renders no role attribute.
        role?: "alert" | "status" | "none";
        /** Shows Carbon's close button; the caller hides the notification. */
        onclose?: () => void;
        /** Carbon's high contrast: a light box on our dark theme. */
        highContrast?: boolean;
    };

    let {
        kind = "error",
        title,
        subtitle,
        role,
        onclose,
        highContrast = false,
        class: className,
        ref = $bindable(null),
        ...restProps
    }: InlineNotificationProps = $props();

    const resolvedRole = $derived(
        role ?? (kind === "error" ? "alert" : "status"),
    );
</script>

<Alert.Root
    bind:ref
    variant={kind === "error" ? "destructive" : kind}
    contrast={highContrast ? "high" : "low"}
    role={resolvedRole === "none" ? undefined : resolvedRole}
    class={onclose ? `pr-12 ${className ?? ""}` : className}
    {...restProps}
>
    {#if kind === "warning"}
        <WarningFilled size={20} />
    {:else if kind === "success"}
        <CheckmarkFilled size={20} />
    {:else}
        <ErrorFilled size={20} />
    {/if}
    <Alert.Title>{title}</Alert.Title>
    {#if subtitle}
        <Alert.Description>{subtitle}</Alert.Description>
    {/if}
    {#if onclose}
        <IconButton
            label="Close"
            class="absolute top-1 right-1"
            onclick={onclose}><Close /></IconButton
        >
    {/if}
</Alert.Root>
