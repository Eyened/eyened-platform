<script lang="ts">
    import { Button } from "$lib/components/ui/button";
    import Browser from "./Browser.svelte";
    import { BrowserContext, type Condition } from "./browserContext.svelte";

    interface Props {
        // Conditions to seed the search with (e.g. Patient Identifier IN [...]).
        initialConditions?: Condition[];
        // Images that should already be selected when the picker opens.
        initialSelectedIds?: string[];
        // Called with the final selection when the user confirms.
        onConfirm: (ids: string[]) => void | Promise<void>;
        // Called when the user dismisses without confirming.
        onCancel?: () => void;
        confirmLabel?: string;
        title?: string;
    }
    let {
        initialConditions,
        initialSelectedIds,
        onConfirm,
        onCancel,
        confirmLabel = "Confirm",
        title = "Browse images",
    }: Props = $props();

    // The picker owns the context so it can read the selection back out.
    const context = new BrowserContext();
    context.urlSync = false;

    let saving = $state(false);

    async function confirm() {
        if (saving) return;
        saving = true;
        try {
            await onConfirm([...context.selectedIds]);
        } finally {
            saving = false;
        }
    }

    function cancel() {
        onCancel?.();
    }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<div
    id="browser-picker"
    tabindex="0"
    onkeydown={(e) => {
        if (e.key === "Escape") cancel();
    }}
>
    <div class="panel browser-light-surface">
        <div class="header">
            <span class="title">{title}</span>
            <div class="actions">
                <Button variant="outline" size="sm" onclick={cancel}
                    >Close</Button
                >
                <Button size="sm" onclick={confirm} disabled={saving}>
                    {confirmLabel}
                </Button>
            </div>
        </div>
        <div class="content">
            <Browser
                {context}
                mode="overlay"
                syncUrl={false}
                {initialConditions}
                {initialSelectedIds}
            />
        </div>
    </div>
</div>

<style>
    div#browser-picker {
        /* Dimmed backdrop; the actual browser is a centered popup card */
        position: fixed;
        z-index: 1000;
        left: 0;
        top: 0;
        bottom: 0;
        right: 0;
        background-color: rgba(0, 0, 0, 0.45);
        backdrop-filter: blur(4px);
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 2.5em;
    }
    div#browser-picker .panel {
        width: min(90vw, 100%);
        height: min(90vh, 100%);
        display: flex;
        flex-direction: column;
        background-color: var(--background);
        border-radius: 12px;
        box-shadow: 0 20px 50px rgba(0, 0, 0, 0.4);
        /* The body scrolls, not the whole panel, so the header stays put */
        overflow: hidden;
    }
    div#browser-picker .header {
        flex: 0 0 auto;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 0.5em 1em;
        border-bottom: 1px solid var(--border);
    }
    div#browser-picker .header .title {
        font-weight: bold;
    }
    div#browser-picker .header .actions {
        display: flex;
        gap: 0.5em;
    }
    div#browser-picker .content {
        flex: 1 1 auto;
        min-height: 0;
        display: flex;
        flex-direction: column;
        overflow-y: auto;
    }
</style>
