<script lang="ts">
    import type { Snippet, Component } from "svelte";
    import type { MouseEventHandler } from "svelte/elements";

    interface Props {
        onclick?: MouseEventHandler<HTMLSpanElement>;
        active?: boolean;
        tooltip?: string;
        theme?: "dark" | "light";
        Icon?: Component;
        iconSnippet?: Snippet;
        size?: string;
    }

    let {
        onclick = undefined,
        active = false,
        tooltip = undefined,
        theme = "dark",
        iconSnippet = undefined,
        Icon = undefined,
        size = "2em",
    }: Props = $props();
</script>

<div class="tooltip" class:link={onclick !== undefined}>
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <span class="icon" class:active {onclick} class:dark={theme == "dark"}>
        {#if iconSnippet}
            {@render iconSnippet?.()}
        {/if}
        {#if Icon}
            <Icon {size} />
        {/if}
    </span>
    {#if tooltip}
        <span class="tooltiptext">{tooltip}</span>
    {/if}
</div>

<style>
    span.icon {
        display: flex;
        align-items: center;
        transition: all 0.3s ease;
    }
    div.tooltip.link > span.icon {
        cursor: pointer;
        color: var(--icon-color);
    }
    div.tooltip.link > span.icon:hover {
        color: var(--icon-hover-color);
    }
    span.icon.dark {
        background-color: transparent;
        color: rgb(175, 175, 175);
        --icon-hover-color: white;
        --icon-color: rgb(175, 175, 175);
    }
    span.icon:not(.dark) {
        background-color: transparent;
        color: rgb(75, 75, 75);
        --icon-hover-color: rgb(0, 0, 0);
        --icon-color: rgb(75, 75, 75);
    }
    span.icon.active {
        background-color: inherit;
        color: white;
    }
    .tooltip {
        position: relative;
        display: inline-block;
    }

    .tooltip .tooltiptext {
        visibility: hidden;
        background-color: rgb(75, 75, 75);
        color: #fff;
        text-align: center;
        border-radius: 2px;
        padding: 0.2em 1em;
        position: absolute;
        z-index: 1;
        opacity: 0;
        transition: opacity 0.3s ease;
        transition-delay: 0.5s;
    }

    .tooltip:hover .tooltiptext {
        visibility: visible;
        opacity: 1;
    }
</style>
