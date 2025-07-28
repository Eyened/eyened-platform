<script lang="ts">
    import { onMount, type Component, type Snippet } from "svelte";

    interface Props {
        active?: boolean;
        disabled?: boolean;
        tooltip?: string | undefined;
        isText?: boolean;
        children?: Snippet;
        Icon?: Component;
        onclick?: () => void;
        onrightclick?: () => void;
        color?: string;
        backgroundColor?: string;
        theme?: "light" | "dark";
        size?: number;
        width?: number;
        height?: number;
    }

    let {
        active = false,
        disabled = false,
        tooltip = undefined,
        isText = false,
        children,
        Icon = undefined,
        onclick = () => {},
        onrightclick = () => {},
        color,
        backgroundColor,
        theme = "dark",
        size,
        width = 1.5,
        height = 1.5,
    }: Props = $props();

    // If size is provided, override width and height
    if (size !== undefined) {
        width = size;
        height = size;
    }

    let tooltipElem: HTMLElement | undefined = $state();
    let tooltiptextElem: HTMLElement | undefined = $state();

    onMount(() => {
        if (!tooltiptextElem || !tooltipElem) return;
        const adjustTooltipPosition = () => {
            const rect = tooltipElem.getBoundingClientRect();
            const textRect = tooltiptextElem.getBoundingClientRect();
            if (rect.left + textRect.width > window.innerWidth) {
                tooltiptextElem.style.right = "0";
            } else {
                tooltiptextElem.style.right = "auto";
            }
        };

        tooltipElem.addEventListener("mouseover", adjustTooltipPosition);
        tooltipElem.addEventListener(
            "mouseout",
            () => (tooltiptextElem.style.right = "auto"),
        );
    });
    function click() {
        if (disabled) return;
        onclick();
    }
    function rightclick(e: MouseEvent) {
        e.preventDefault();
        if (disabled) return;
        onrightclick();
    }
</script>

<div class="tooltip {theme}" bind:this={tooltipElem}>
    <!-- svelte-ignore a11y_click_events_have_key_events -->
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <span
        class="icon"
        class:isText
        class:active
        class:disabled
        onclick={click}
        oncontextmenu={rightclick}
        style:color
        style:background-color={backgroundColor}
        style:width="{width}em"
        style:height="{height}em"
    >
        {#if children}
            {@render children()}
        {/if}
        {#if Icon}
            <Icon />
        {/if}
    </span>
    {#if tooltip}
        <span class="tooltiptext" bind:this={tooltiptextElem}>{tooltip}</span>
    {/if}
</div>

<style lang="scss">
    .light {
        --icon-color: rgba(0, 0, 0, 0.6);
        --icon-hover-color: rgba(0, 0, 0, 0.8);
        --icon-active-color: rgba(0, 0, 0, 1);
        --icon-disabled-color: rgba(0, 0, 0, 0.1);
        --icon-hover-bg: rgba(0, 0, 0, 0.1);
        --icon-active-bg: rgba(0, 0, 0, 0.2);
        --tooltip-bg: #333;
        --tooltip-color: #fff;
    }

    .dark {
        --icon-color: rgba(255, 255, 255, 0.6);
        --icon-hover-color: rgba(255, 255, 255, 0.8);
        --icon-active-color: rgba(255, 255, 255, 1);
        --icon-disabled-color: rgba(255, 255, 255, 0.1);
        --icon-hover-bg: rgba(255, 255, 255, 0.1);
        --icon-active-bg: rgba(155, 255, 255, 0.4);
        --tooltip-bg: #555;
        --tooltip-color: #fff;
    }

    span.icon {
        display: flex;
        align-items: center;
        cursor: pointer;
        color: var(--icon-color);
        margin: 0.2em;
        padding: 0.2em;
        border-radius: 50%;
        transition: all 0.3s ease;
    }

    span.icon.isText {
        width: auto !important;
        height: auto !important;
    }

    span.icon:hover {
        border-radius: 2px;
        color: var(--icon-hover-color);
        background-color: var(--icon-hover-bg);
    }

    span.icon.active {
        border-radius: 2px;
        color: var(--icon-active-color);
        background-color: var(--icon-active-bg);
    }

    span.icon.disabled {
        cursor: not-allowed;
        border-radius: 2px;
        color: var(--icon-disabled-color);
        background-color: transparent;
    }

    .tooltip {
        position: relative;
        display: inline-block;
    }

    .tooltiptext {
        pointer-events: none;
    }

    .tooltip .tooltiptext {
        background-color: var(--tooltip-bg);
        opacity: 0;
        visibility: hidden;
        color: var(--tooltip-color);
        text-align: center;
        border-radius: 2px;
        padding: 0.2em 1em;
        position: absolute;
        z-index: 10;
        transition: opacity 0.3s ease;
        transition-delay: 0.5s;
    }

    .tooltip:hover .tooltiptext {
        visibility: visible;
        opacity: 1;
    }
</style>
