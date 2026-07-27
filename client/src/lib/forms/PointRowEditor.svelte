<script lang="ts">
    import { Input } from "$lib/components/ui/input";
    import type { ImagePoint } from "$lib/forms/pointSchema";

    export type PointRow = { publicId: string; index: number; pt: ImagePoint };

    interface Props {
        row: PointRow;
        canEdit: boolean;
        hasExtras: boolean;
        enumExtras: { key: string; values: readonly string[] }[];
        stringExtraKeys: string[];
        indexApplicable: (pt: ImagePoint) => boolean;
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
        onCollapse: () => void;
    }

    let {
        row,
        canEdit,
        hasExtras,
        enumExtras,
        stringExtraKeys,
        indexApplicable,
        onUpdateCoord,
        onUpdateExtra,
        onCollapse,
    }: Props = $props();
</script>

<div class="editor">
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
                <label>
                    {key}
                    <Input
                        disabled={!canEdit}
                        value={String(row.pt[key] ?? "")}
                        oninput={(e) =>
                            onUpdateExtra(
                                row.publicId,
                                row.index,
                                key,
                                (e.currentTarget as HTMLInputElement).value,
                            )}
                    />
                </label>
            {/each}
        </div>
    {/if}

    <button type="button" class="collapse" onclick={onCollapse}> Done </button>
</div>

<style>
    .editor {
        display: flex;
        flex-direction: column;
        gap: 0.45em;
        margin-left: 0.25em;
        padding: 0.5em;
        border-left: 2px solid rgba(255, 255, 255, 0.25);
        background: rgba(255, 255, 255, 0.04);
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
    .collapse {
        align-self: flex-start;
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
