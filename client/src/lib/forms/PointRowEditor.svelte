<script lang="ts">
    import { Input } from "$lib/components/ui/input";
    import type { ImagePoint } from "$lib/forms/pointSchema";
    import { Trash } from "$lib/viewer-window/icons/icons";

    export type PointRow = { publicId: string; index: number; pt: ImagePoint };

    interface Props {
        row: PointRow;
        canEdit: boolean;
        hasExtras: boolean;
        enumExtras: { key: string; values: readonly string[] }[];
        stringExtraKeys: string[];
        indexApplicable: (pt: ImagePoint) => boolean;
        coordLabel: string;
        onUpdateCoord: (
            pid: string,
            index: number,
            key: "x" | "y" | "index",
            raw: string,
        ) => void;
        onUpdateExtra: (
            pid: string,
            index: number,
            key: string,
            extraValue: string,
        ) => void;
        onRemove: () => void;
        onCollapse: () => void;
    }

    let {
        row,
        canEdit,
        hasExtras,
        enumExtras,
        stringExtraKeys,
        indexApplicable,
        coordLabel,
        onUpdateCoord,
        onUpdateExtra,
        onRemove,
        onCollapse,
    }: Props = $props();
</script>

<div class="editor">
    <div class="editor-header">
        <span class="editor-label" title={coordLabel}>{coordLabel}</span>
        <div class="editor-actions">
            {#if canEdit}
                <button
                    type="button"
                    class="icon-btn"
                    title="Remove point"
                    aria-label="Remove point"
                    onclick={onRemove}
                >
                    <Trash size="1.1em" />
                </button>
            {/if}
            <button type="button" class="collapse" onclick={onCollapse}>
                Done
            </button>
        </div>
    </div>

    <div class="editor-coords">
        <label>
            x
            <Input
                type="number"
                step="1"
                disabled={!canEdit}
                value={Math.round(row.pt.x)}
                oninput={(e) =>
                    onUpdateCoord(
                        row.publicId,
                        row.index,
                        "x",
                        (e.currentTarget as HTMLInputElement).value,
                    )}
            />
        </label>
        <label>
            y
            <Input
                type="number"
                step="1"
                disabled={!canEdit}
                value={Math.round(row.pt.y)}
                oninput={(e) =>
                    onUpdateCoord(
                        row.publicId,
                        row.index,
                        "y",
                        (e.currentTarget as HTMLInputElement).value,
                    )}
            />
        </label>
        {#if indexApplicable(row.pt)}
            <label title="B-scan index; empty = enface (null)">
                i
                <Input
                    type="number"
                    step="1"
                    disabled={!canEdit}
                    value={typeof row.pt.index === "number"
                        ? Math.round(row.pt.index)
                        : ""}
                    placeholder="null"
                    oninput={(e) =>
                        onUpdateCoord(
                            row.publicId,
                            row.index,
                            "index",
                            (e.currentTarget as HTMLInputElement).value,
                        )}
                />
            </label>
        {/if}
    </div>

    {#if hasExtras}
        <div class="editor-extras">
            {#each enumExtras as extra (extra.key)}
                <label>
                    {extra.key}
                    <select
                        disabled={!canEdit}
                        value={String(row.pt[extra.key] ?? "")}
                        onchange={(e) =>
                            onUpdateExtra(
                                row.publicId,
                                row.index,
                                extra.key,
                                (e.currentTarget as HTMLSelectElement).value,
                            )}
                    >
                        <option value="">—</option>
                        {#each extra.values as opt (opt)}
                            <option value={opt}>{opt}</option>
                        {/each}
                    </select>
                </label>
            {/each}
            {#each stringExtraKeys as key (key)}
                {@const extraVal = row.pt[key]}
                <label>
                    {key}
                    <!-- Native controlled input: shadcn Input's $bindable+bind:value
                         does not reliably show one-way value={...} updates. -->
                    <input
                        type="text"
                        class="extra-input"
                        disabled={!canEdit}
                        value={typeof extraVal === "string" ? extraVal : ""}
                        oninput={(e) =>
                            onUpdateExtra(
                                row.publicId,
                                row.index,
                                key,
                                e.currentTarget.value,
                            )}
                    />
                </label>
            {/each}
        </div>
    {/if}
</div>

<style>
    .editor {
        display: flex;
        flex-direction: column;
        gap: 0.45em;
        margin-left: 0.15em;
        padding: 0.5em;
        border: 1px solid rgba(0, 0, 0, 0.3);
        border-radius: 0.35em;
        background: rgba(255, 255, 255, 0.07);
    }
    .editor-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.5em;
    }
    .editor-label {
        font-family: monospace;
        font-size: 0.9em;
        opacity: 0.9;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        min-width: 0;
    }
    .editor-actions {
        display: flex;
        align-items: center;
        gap: 0.35em;
        flex-shrink: 0;
    }
    .editor-coords,
    .editor-extras {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5em 0.75em;
        align-items: center;
    }
    .editor label {
        display: flex;
        align-items: center;
        gap: 0.35em;
        font-size: 0.9em;
    }
    .extra-input {
        min-width: 8em;
        padding: 0.2em 0.4em;
        font: inherit;
        color: inherit;
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.28);
        border-radius: 3px;
    }
    .extra-input:disabled {
        opacity: 0.55;
    }
    .icon-btn {
        appearance: none;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: transparent;
        border: 1px solid transparent;
        border-radius: 3px;
        color: inherit;
        cursor: pointer;
        opacity: 0.75;
        padding: 0.15em;
        margin: 0;
    }
    .icon-btn:hover {
        opacity: 1;
        background: rgba(255, 255, 255, 0.08);
        border-color: rgba(255, 255, 255, 0.25);
    }
    .collapse {
        appearance: none;
        background: transparent;
        border: 1px solid rgba(255, 255, 255, 0.25);
        border-radius: 3px;
        color: inherit;
        cursor: pointer;
        font-size: 0.8em;
        padding: 0.15em 0.5em;
    }
    .collapse:hover {
        background: rgba(255, 255, 255, 0.08);
    }
</style>
