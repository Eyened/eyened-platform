<script lang="ts">
    import * as Tooltip from "$lib/components/ui/tooltip/index.js";
    import { cn } from "$lib/utils.js";
    import { mergeProps } from "bits-ui";
    import Close from "carbon-icons-svelte/lib/Close.svelte";
    import { tagClasses } from "./tag.svelte";

    let {
        text,
        title = "Dismiss",
        ondismiss,
    }: { text: string; title?: string; ondismiss: () => void } = $props();
</script>

<span data-slot="tag" class={cn(tagClasses, "pe-0")}>
    <span class="truncate">{text}</span>
    <Tooltip.Provider delayDuration={100}>
        <Tooltip.Root>
            <Tooltip.Trigger>
                {#snippet child({ props })}
                    <button
                        {...mergeProps(props, { onclick: ondismiss })}
                        type="button"
                        aria-label={title}
                        class="ms-0.5 flex size-6 shrink-0 cursor-pointer items-center justify-center rounded-full hover:bg-tag-hover-gray"
                    >
                        <Close aria-hidden="true" />
                    </button>
                {/snippet}
            </Tooltip.Trigger>
            <Tooltip.Content size="icon">{title}</Tooltip.Content>
        </Tooltip.Root>
    </Tooltip.Provider>
</span>
