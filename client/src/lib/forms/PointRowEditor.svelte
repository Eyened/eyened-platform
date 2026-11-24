<script lang="ts" module>
    import type { ImagePoint } from "$lib/forms/pointSchema";

    export type PointRow = { publicId: string; index: number; pt: ImagePoint };
</script>

<script lang="ts">
    import { Button } from "$lib/components/ui/button/index.js";
    import { Dropdown } from "$lib/components/ui/dropdown/index.js";
    import { NumberInput } from "$lib/components/ui/number-input/index.js";
    import { TextInput } from "$lib/components/ui/text-input/index.js";
    import type { PointEnumExtra } from "$lib/forms/pointSchema";
    import TrashCan from "carbon-icons-svelte/lib/TrashCan.svelte";

    interface Props {
        row: PointRow;
        /** The marker number, as the image labels it. */
        number: number;
        canEdit: boolean;
        hasExtras: boolean;
        enumExtras: readonly PointEnumExtra[];
        stringExtraKeys: string[];
        indexApplicable: (pt: ImagePoint) => boolean;
        /** When false (volume schemas), an empty B-scan is an error and nothing is saved. */
        allowNullIndex?: boolean;
        /** Why the viewer didn't move to this point. */
        hint?: string | null;
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
        number,
        canEdit,
        hasExtras,
        enumExtras,
        stringExtraKeys,
        indexApplicable,
        allowNullIndex = true,
        hint = null,
        onUpdateCoord,
        onUpdateExtra,
        onRemove,
        onCollapse,
    }: Props = $props();

    // The typed text while it is invalid; nothing is saved then.
    let invalidText = $state<string | null>(null);

    // Shown from 1 like the viewer's slice counter; stored from 0.
    function bscanText(): string {
        if (invalidText !== null) return invalidText;
        return typeof row.pt.index === "number"
            ? String(Math.round(row.pt.index) + 1)
            : "";
    }

    function setBscan(raw: string) {
        const n = Number(raw);
        const empty = raw.trim() === "";
        invalidText =
            (empty && !allowNullIndex) ||
            (!empty && Number.isFinite(n) && n < 1)
                ? raw
                : null;
        if (invalidText !== null) return;
        onUpdateCoord(
            row.publicId,
            row.index,
            "index",
            empty || !Number.isFinite(n) ? raw : String(n - 1),
        );
    }
</script>

<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<div
    role="group"
    aria-label="Point {number}"
    class="flex flex-col gap-4 border-s-2 border-border-subtle-01 py-2 ps-4"
    onkeydown={(e) => {
        if (e.key === "Escape") {
            e.stopPropagation();
            onCollapse();
        }
    }}
>
    {#if hint}
        <p class="text-helper-text-01 text-text-secondary">{hint}</p>
    {/if}
    <p class="text-heading-compact-01 text-text-primary">Point {number}</p>
    <div class="flex flex-wrap gap-4">
        <NumberInput
            size="sm"
            labelText="x"
            readonly={!canEdit}
            bind:value={
                () => String(Math.round(row.pt.x)),
                (raw) => onUpdateCoord(row.publicId, row.index, "x", raw)
            }
        />
        <NumberInput
            size="sm"
            labelText="y"
            readonly={!canEdit}
            bind:value={
                () => String(Math.round(row.pt.y)),
                (raw) => onUpdateCoord(row.publicId, row.index, "y", raw)
            }
        />
        {#if indexApplicable(row.pt)}
            <NumberInput
                size="sm"
                labelText="B-scan"
                readonly={!canEdit}
                required={!allowNullIndex}
                helperText={allowNullIndex ? "Empty = en-face" : undefined}
                invalidText={invalidText !== null
                    ? "Enter a B-scan number."
                    : undefined}
                bind:value={bscanText, setBscan}
            />
        {/if}
    </div>
    {#if hasExtras}
        <div class="flex flex-wrap gap-4">
            {#each enumExtras as extra (extra.key)}
                {@const raw = row.pt[extra.key]}
                {@const grade =
                    typeof raw === "string" && extra.values.includes(raw)
                        ? raw
                        : ""}
                {#if canEdit}
                    <!-- A required grade has no None, so an unset point stays visibly unset. -->
                    <Dropdown
                        size="sm"
                        labelText={extra.key}
                        placeholder="Choose an option"
                        items={[
                            ...(extra.required
                                ? []
                                : [{ id: "", text: "None" }]),
                            ...extra.values.map((v) => ({ id: v, text: v })),
                        ]}
                        selectedId={grade || (extra.required ? undefined : "")}
                        onselect={(id) =>
                            onUpdateExtra(
                                row.publicId,
                                row.index,
                                extra.key,
                                id,
                            )}
                    />
                {:else}
                    <TextInput labelText={extra.key} readonly value={grade} />
                {/if}
            {/each}
            {#each stringExtraKeys as key (key)}
                {@const extraVal = row.pt[key]}
                <TextInput
                    labelText={key}
                    readonly={!canEdit}
                    bind:value={
                        () => (typeof extraVal === "string" ? extraVal : ""),
                        (v) => onUpdateExtra(row.publicId, row.index, key, v)
                    }
                />
            {/each}
        </div>
    {/if}
    <div class="flex gap-2">
        {#if canEdit}
            <Button variant="danger-ghost" size="sm" onclick={onRemove}
                >Delete point<TrashCan /></Button
            >
        {/if}
        <Button variant="outline" size="sm" onclick={onCollapse}>Done</Button>
    </div>
</div>
