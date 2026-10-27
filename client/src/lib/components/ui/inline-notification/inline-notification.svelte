<script lang="ts">
    import * as Alert from "$lib/components/ui/alert/index.js";
    import type { WithElementRef } from "$lib/utils.js";
    import ErrorFilled from "carbon-icons-svelte/lib/ErrorFilled.svelte";
    import type { HTMLAttributes } from "svelte/elements";

    // Carbon InlineNotification API, error kind only, no close button.
    type InlineNotificationProps = Omit<
        WithElementRef<HTMLAttributes<HTMLDivElement>>,
        "title" | "role" | "children"
    > & {
        title: string; // no trailing period
        subtitle?: string;
        role?: "alert" | "none"; // "none" renders no role attribute
    };

    let {
        title,
        subtitle,
        role = "alert",
        ref = $bindable(null),
        ...restProps
    }: InlineNotificationProps = $props();
</script>

<Alert.Root
    bind:ref
    role={role === "alert" ? "alert" : undefined}
    {...restProps}
>
    <ErrorFilled size={20} />
    <Alert.Title>{title}</Alert.Title>
    {#if subtitle}
        <Alert.Description>{subtitle}</Alert.Description>
    {/if}
</Alert.Root>
