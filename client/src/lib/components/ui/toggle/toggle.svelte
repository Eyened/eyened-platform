<script lang="ts">
    import { Switch as SwitchPrimitive } from "bits-ui";
    import { cn, type WithoutChildrenOrChild } from "$lib/utils.js";

    let {
        ref = $bindable(null),
        checked = $bindable(false),
        class: className,
        ...restProps
    }: WithoutChildrenOrChild<SwitchPrimitive.RootProps> = $props();
</script>

<!-- Carbon small toggle: 32 × 16 track, 10 px handle, a tickmark when on so the state never rests on colour. -->
<SwitchPrimitive.Root
    bind:ref
    bind:checked
    data-slot="toggle"
    class={cn(
        "group relative inline-flex h-4 w-8 shrink-0 cursor-pointer items-center rounded-full bg-toggle-off data-[state=checked]:bg-support-success",
        className,
    )}
    {...restProps}
>
    <SwitchPrimitive.Thumb
        class="pointer-events-none flex size-2.5 translate-x-[3px] items-center justify-center rounded-full bg-icon-on-color data-[state=checked]:translate-x-[19px]"
    >
        <svg
            viewBox="0 0 6 5"
            class="hidden h-[5px] w-[6px] fill-support-success group-data-[state=checked]:block"
            aria-hidden="true"
            ><path d="M2.2 2.7L5 0 6 1 2.2 5 0 2.7 1 1.5z" /></svg
        >
    </SwitchPrimitive.Thumb>
</SwitchPrimitive.Root>
