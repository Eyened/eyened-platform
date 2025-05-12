<script lang="ts">
    import Close from "$lib/viewer-window/icons/Close.svelte";
    import MainIcon from "$lib/viewer-window/icons/MainIcon.svelte";
    import type { ComponentDef } from "$lib/data-loading/globalContext.svelte";

    interface Props {
        componentDef: ComponentDef;
        close: () => void;
    }
    let { componentDef, close }: Props = $props();

    function keydown(e: KeyboardEvent) {
        if (e.key == "Escape") {
            close();
        }
    }
</script>

<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
    class="popup"
    tabindex="0"
    onkeydown={keydown}
    onpointerenter={(e) => e.target.focus()}
>
    <div class="popup-content">
        <div class="popup-header">
            {#snippet icon()}
                <Close size="2em" />
            {/snippet}
            <MainIcon onclick={close} {icon} theme="light" />
        </div>
        <div class="popup-body">
            <componentDef.component {...componentDef.props} />
        </div>
    </div>
</div>

<style>
    .popup {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(255, 255, 255, 0.95);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 1000;
    }

    .popup-content {
        background-color: white;
        border-radius: 2px;
        display: flex;
        flex-direction: column;
        max-height: 90%;
        width: 90%;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
    }

    .popup-header {
        display: flex;
        flex: 0;
        background-color: var(--browser-background);
        border-bottom: 1px solid #ddd;
        border-radius: 2px 2px 0 0;
    }

    .popup-body {
        flex: 1;
        overflow: auto;
    }
</style>
