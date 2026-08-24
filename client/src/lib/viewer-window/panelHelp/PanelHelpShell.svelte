<script lang="ts">
    import { Button } from "$lib/components/ui/button";
    import type { Snippet } from "svelte";

    interface Props {
        title: string;
        onClose: () => void;
        children: Snippet;
    }

    let { title, onClose, children }: Props = $props();

    let backdropEl: HTMLDivElement | undefined = $state(undefined);

    $effect(() => {
        if (backdropEl) backdropEl.focus();
    });
</script>

<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<div
    class="backdrop"
    bind:this={backdropEl}
    role="dialog"
    aria-modal="true"
    aria-labelledby="panel-help-title"
    tabindex="-1"
    onkeydown={(e) => {
        if (e.key === "Escape") onClose();
    }}
    onpointerdown={(e) => {
        if (e.target === e.currentTarget) onClose();
    }}
>
    <div class="dialog">
        <header class="header">
            <h1 id="panel-help-title">{title}</h1>
            <Button variant="outline" size="sm" onclick={onClose}>Close</Button>
        </header>

        <div class="body">
            {@render children()}
        </div>
    </div>
</div>

<style>
    .backdrop {
        position: fixed;
        inset: 0;
        z-index: 2000;
        display: flex;
        align-items: flex-start;
        justify-content: center;
        padding: 2em 1em;
        background-color: rgba(0, 0, 0, 0.55);
        backdrop-filter: blur(4px);
        overflow-y: auto;
        color: #1a1a1a;
    }

    .dialog {
        width: min(100%, 45rem);
        max-height: calc(100vh - 4em);
        display: flex;
        flex-direction: column;
        background: rgba(255, 255, 255, 0.97);
        border-radius: 4px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
        overflow: hidden;
    }

    .header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 1em;
        padding: 0.75em 1em;
        border-bottom: 1px solid #ddd;
        flex: 0 0 auto;
    }

    h1 {
        margin: 0;
        font-size: 1.1rem;
        font-weight: 600;
    }

    .body {
        padding: 1em 1.25em 1.5em;
        overflow-y: auto;
        flex: 1 1 auto;
    }

    .body :global(p.intro) {
        margin: 0 0 1em;
        color: #444;
        line-height: 1.5;
        font-size: 0.92rem;
    }

    .body :global(section) {
        margin-bottom: 1.25em;
    }

    .body :global(section:last-child) {
        margin-bottom: 0;
    }

    .body :global(h2) {
        font-size: 0.95rem;
        font-weight: 600;
        margin: 0 0 0.4em;
        padding-bottom: 0.2em;
        border-bottom: 1px solid #ddd;
    }

    .body :global(p) {
        margin: 0 0 0.5em;
        font-size: 0.92rem;
        line-height: 1.45;
        color: #333;
    }

    .body :global(ul) {
        margin: 0;
        padding-left: 1.25em;
        font-size: 0.92rem;
        line-height: 1.45;
        color: #333;
    }

    .body :global(li + li) {
        margin-top: 0.25em;
    }

    .body :global(dl) {
        margin: 0;
    }

    .body :global(.row) {
        display: grid;
        grid-template-columns: 1fr auto;
        gap: 1em;
        padding: 0.25em 0;
        align-items: baseline;
    }

    .body :global(dt) {
        margin: 0;
        font-size: 0.92rem;
    }

    .body :global(dd) {
        margin: 0;
        text-align: right;
    }

    .body :global(kbd) {
        display: inline-block;
        padding: 0.12em 0.45em;
        font-family: inherit;
        font-size: 0.85rem;
        background: #f3f4f6;
        border: 1px solid #d1d5db;
        border-radius: 4px;
        white-space: nowrap;
    }

    .body :global(table.help-table) {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.92rem;
        line-height: 1.45;
        color: #333;
    }

    .body :global(table.help-table th),
    .body :global(table.help-table td) {
        padding: 0.45em 0.6em;
        border-bottom: 1px solid #e5e7eb;
        vertical-align: top;
        text-align: left;
    }

    .body :global(table.help-table th) {
        font-weight: 600;
        background: #f9fafb;
        color: #111;
    }

    .body :global(table.help-table th.shortcut),
    .body :global(table.help-table td.shortcut) {
        width: 5.5em;
        white-space: nowrap;
        text-align: center;
    }

    .body :global(table.help-table td.shortcut .none) {
        color: #9ca3af;
        font-size: 0.85rem;
    }

    .body :global(table.help-table tbody tr:last-child td) {
        border-bottom: none;
    }

    .body :global(details.subsection) {
        margin: 0.35em 0 0;
        border: 1px solid #e5e7eb;
        border-radius: 4px;
        background: #fafafa;
    }

    .body :global(details.subsection + details.subsection) {
        margin-top: 0.45em;
    }

    .body :global(details.subsection summary) {
        padding: 0.45em 0.65em;
        font-size: 0.9rem;
        font-weight: 600;
        color: #111;
        cursor: pointer;
        list-style: none;
        user-select: none;
    }

    .body :global(details.subsection summary::-webkit-details-marker) {
        display: none;
    }

    .body :global(details.subsection summary::before) {
        content: "▸";
        display: inline-block;
        margin-right: 0.45em;
        font-size: 0.85em;
        color: #6b7280;
        transition: transform 0.15s ease;
    }

    .body :global(details.subsection[open] summary::before) {
        transform: rotate(90deg);
    }

    .body :global(details.subsection .subsection-body) {
        padding: 0 0.65em 0.65em;
        border-top: 1px solid #e5e7eb;
    }

    .body :global(details.subsection .subsection-body > :first-child) {
        margin-top: 0.5em;
    }

    .body :global(details.subsection .subsection-body > :last-child) {
        margin-bottom: 0;
    }
</style>
