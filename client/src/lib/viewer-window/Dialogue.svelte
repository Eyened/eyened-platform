<script lang="ts">
    import {
        dialogueManager,
        type Dialogue,
    } from "$lib/dialogue/DialogueManager";

    const dialogue = dialogueManager.dialogue;

    function props(dialogue: Dialogue) {
        return {
            ...dialogue.props,
            resolve: dialogue.resolve,
            reject: dialogue.reject,
        };
    }
</script>

{#if $dialogue}
    <div class="overlay component">
        <div class="dialogue-container">
            <svelte:component
                this={$dialogue.component}
                {...props($dialogue)}
            />
        </div>
    </div>
{/if}

<style>
    div {
        display: flex;
    }
    .overlay {
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        background-color: rgba(255, 255, 255, 0.8);
        z-index: 9999;
        display: flex;
        justify-content: center;
        align-items: center;
    }
    .overlay.component {
        pointer-events: none;
        background-color: transparent;
    }
    .overlay.component > * {
        pointer-events: auto;
    }
    .dialogue-container {
        /* width: 400px; */
        background-color: #fff;
        border-radius: 4px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
        padding: 16px;
        flex-direction: column;
    }
</style>
