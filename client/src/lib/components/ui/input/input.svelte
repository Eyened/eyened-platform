<script lang="ts">
    import type {
        HTMLInputAttributes,
        HTMLInputTypeAttribute,
    } from "svelte/elements";
    import { cn, type WithElementRef } from "$lib/utils.js";

    type InputType = Exclude<HTMLInputTypeAttribute, "file">;

    type Props = WithElementRef<
        Omit<HTMLInputAttributes, "type"> &
            (
                | { type: "file"; files?: FileList }
                | { type?: InputType; files?: undefined }
            )
    >;

    let {
        ref = $bindable(null),
        value = $bindable(),
        type,
        files = $bindable(),
        class: className,
        ...restProps
    }: Props = $props();

    // Carbon text input; values from @carbon/styles components/text-input. Focus ring comes from app.css.
    const inputClasses =
        "h-10 w-full min-w-0 border-0 border-b border-border-strong-01 bg-field-01 px-4 text-body-compact-01 text-text-primary placeholder:text-text-placeholder aria-invalid:not-focus:outline-2 aria-invalid:not-focus:-outline-offset-2 aria-invalid:not-focus:outline-support-error disabled:cursor-not-allowed disabled:border-transparent disabled:text-text-disabled";
</script>

{#if type === "file"}
    <input
        bind:this={ref}
        data-slot="input"
        class={cn(inputClasses, className)}
        type="file"
        bind:files
        bind:value
        {...restProps}
    />
{:else}
    <input
        bind:this={ref}
        data-slot="input"
        class={cn(inputClasses, className)}
        {type}
        bind:value
        {...restProps}
    />
{/if}
