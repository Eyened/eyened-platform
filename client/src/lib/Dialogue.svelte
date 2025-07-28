<script lang="ts">
    import type { ComponentDef } from "./data-loading/globalContext.svelte";

    interface Props {
        content: ComponentDef | string;
        close: () => void;
    }
    let { content, close }: Props = $props();
    
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
        {#if typeof content === "string"}
            {content}
            <div class="popup-footer">
                <button onclick={close}>Close</button>
            </div>
        {:else}
            <content.component {...content.props} close={close} />
        {/if}
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
        display: flex;
        flex-direction: column;
    }

    .popup-content {
        padding: 1em;
        
        background-color: white;
        border-radius: 2px;
        display: flex;
        flex-direction: column;
        align-items: center;
        
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
    }
    .popup-footer {
        display: flex;        
        padding: 0.5em;
    }
</style>
