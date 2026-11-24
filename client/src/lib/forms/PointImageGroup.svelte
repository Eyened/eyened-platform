<script lang="ts" module>
    import type { ImagePoint } from "$lib/forms/pointSchema";

    /** One place in an image's list; `pt` is null where a matched landmark was deleted. */
    export type PointSlot = {
        publicId: string;
        index: number;
        pt: ImagePoint | null;
    };
</script>

<script lang="ts">
    import type { PointEnumExtra } from "$lib/forms/pointSchema";
    import PointRowEditor, {
        type PointRow,
    } from "$lib/forms/PointRowEditor.svelte";
    import { cn } from "$lib/utils.js";

    interface Props {
        group: { publicId: string; rows: PointSlot[] };
        /** The image in viewer words: "OD · OCT · 2024-03-12". */
        heading: string;
        expandedKey: string | null;
        canEdit: boolean;
        hasExtras: boolean;
        enumExtras: readonly PointEnumExtra[];
        stringExtraKeys: string[];
        rowKey: (row: PointSlot) => string;
        /** "B-scan 37", "en-face", or null when the field has no B-scans. */
        bscanText: (pt: ImagePoint) => string | null;
        extraPreview: (pt: ImagePoint) => string;
        indexApplicable: (pt: ImagePoint) => boolean;
        allowNullIndex?: boolean;
        hint: string | null;
        onGoTo: (row: PointRow) => void;
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
        onRemovePoint: (pid: string, index: number) => void;
        onCollapse: () => void;
    }

    let {
        group,
        heading,
        expandedKey,
        canEdit,
        hasExtras,
        enumExtras,
        stringExtraKeys,
        rowKey,
        bscanText,
        extraPreview,
        indexApplicable,
        allowNullIndex = true,
        hint,
        onGoTo,
        onUpdateCoord,
        onUpdateExtra,
        onRemovePoint,
        onCollapse,
    }: Props = $props();

    const count = $derived(group.rows.filter((r) => r.pt).length);
</script>

<div class="flex flex-col">
    <div class="flex h-8 items-center justify-between gap-2">
        <p
            class="truncate text-heading-compact-01 text-text-primary"
            title={group.publicId}
        >
            {heading}
        </p>
        <p class="shrink-0 text-label-01 text-text-secondary">
            {count === 1 ? "1 point" : `${count} points`}
        </p>
    </div>
    <ul class="flex flex-col">
        {#each group.rows as slot (rowKey(slot))}
            <li>
                {#if slot.pt}
                    {@const row = {
                        publicId: slot.publicId,
                        index: slot.index,
                        pt: slot.pt,
                    }}
                    {@const open = expandedKey === rowKey(slot)}
                    <!-- The name is the visible text, so voice control can say what it sees. -->
                    <button
                        type="button"
                        data-row-key={rowKey(slot)}
                        aria-expanded={open}
                        class={cn(
                            "flex h-8 w-full items-center gap-2 px-2 text-start text-body-compact-01 text-text-primary hover:bg-layer-hover-01",
                            open && "bg-layer-selected-01",
                        )}
                        onclick={() => onGoTo(row)}
                    >
                        <span class="w-16 shrink-0"
                            ><span class="sr-only">Point </span>{slot.index +
                                1}</span
                        >
                        <span class="w-16 shrink-0"
                            ><span class="sr-only">x </span>{Math.round(
                                slot.pt.x,
                            )}</span
                        >
                        <span class="w-16 shrink-0"
                            ><span class="sr-only">y </span>{Math.round(
                                slot.pt.y,
                            )}</span
                        >
                        {#if bscanText(slot.pt)}
                            <span class="w-24 shrink-0"
                                >{bscanText(slot.pt)}</span
                            >
                        {/if}
                        <span
                            class="min-w-0 flex-1 truncate text-text-secondary"
                            >{extraPreview(slot.pt).trim()}</span
                        >
                    </button>
                    {#if open}
                        <PointRowEditor
                            {row}
                            number={slot.index + 1}
                            {canEdit}
                            {hasExtras}
                            {enumExtras}
                            {stringExtraKeys}
                            {indexApplicable}
                            {allowNullIndex}
                            {hint}
                            {onUpdateCoord}
                            {onUpdateExtra}
                            onRemove={() =>
                                onRemovePoint(slot.publicId, slot.index)}
                            {onCollapse}
                        />
                    {/if}
                {:else}
                    <p
                        class="flex h-8 items-center px-2 text-body-compact-01 text-text-disabled"
                    >
                        {slot.index + 1} · deleted
                    </p>
                {/if}
            </li>
        {/each}
    </ul>
</div>
