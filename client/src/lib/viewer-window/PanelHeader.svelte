<script lang="ts">
    import type { PanelName } from "$lib/viewer/viewer-utils";
    import { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import CircleHelp from "@lucide/svelte/icons/circle-help";
    import { getContext, type Component } from "svelte";
    import MainIcon from "./icons/MainIcon.svelte";
    import { PanelIcon } from "./icons/icons";
    import PanelHelpShell from "./panelHelp/PanelHelpShell.svelte";

    interface Props {
        text: string;
        Icon: Component;
        panelName: PanelName;
        Help?: Component;
    }
    let { text = "", Icon, panelName, Help }: Props = $props();

    const viewerContext = getContext<ViewerContext>("viewerContext");
    const { activePanels } = viewerContext;
    let active = $derived(activePanels.has(panelName));

    let showHelp = $state(false);

    const helpTitle = $derived(
        panelName === "ETDRS" ? "ETDRS grid panel" : `${text} panel`,
    );

    function toggle() {
        if (activePanels.has(panelName)) {
            activePanels.delete(panelName);
        } else {
            activePanels.add(panelName);
        }
    }

    function openHelp() {
        showHelp = true;
    }

    function closeHelp() {
        showHelp = false;
    }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<h3 class:active onclick={toggle}>
    <span id="chev">
        {#if active}
            &#9660;
        {:else}
            &#9654;
        {/if}
    </span>
    <MainIcon {active} {Icon} size="1.75em" />
    <span class="title">{text}</span>
    {#if Help}
        <span class="help-slot">
            <PanelIcon tooltip="Help" onclick={openHelp} size={1.4}>
                <CircleHelp size={18} strokeWidth={2} />
            </PanelIcon>
        </span>
    {/if}
</h3>

{#if showHelp && Help}
    <PanelHelpShell title={helpTitle} onClose={closeHelp}>
        <Help />
    </PanelHelpShell>
{/if}

<style>
    h3 {
        display: flex;
        align-items: center;
        border-bottom: 1px solid rgb(45, 45, 45);
        margin: 0;
        font-size: small;
    }
    span#chev {
        width: 1em;
        flex: 0 0 auto;
    }
    span.title {
        margin-left: 0.5em;
        flex: 1 1 auto;
        min-width: 0;
    }
    span.help-slot {
        flex: 0 0 auto;
        margin-left: auto;
        margin-right: 0.25em;
        display: flex;
        align-items: center;
    }
    h3:hover {
        cursor: pointer;
        background-color: rgb(45, 45, 45);
    }
    h3.active {
        background-color: rgb(48, 102, 102);
        color: white;
    }
</style>
