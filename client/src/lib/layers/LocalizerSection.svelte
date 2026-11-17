<!--
@component
Layers › Localizer lines for the selected viewport: one Off / Current / All switcher for every OCT this image localizes, and a line per OCT.
-->
<script lang="ts">
    import { ToggleGroup } from "$lib/components/ui/toggle-group/index.js";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import type { LocalizerMode } from "$lib/workspace/workspaceRules";
    import { getContext } from "svelte";
    import LayerSection from "./LayerSection.svelte";
    import type { LocalizerLines } from "./localizerLines.svelte";
    import { octLabel } from "./octLabel";

    let {
        localizer,
        open,
        ontoggle,
    }: {
        localizer: LocalizerLines;
        open: boolean;
        ontoggle: () => void;
    } = $props();

    const win = getContext<ViewerContext>("viewerContext").viewerWindowContext;

    const MODES = [
        { value: "off", text: "Off", label: "Off" },
        { value: "current", text: "Current", label: "Current slice" },
        { value: "all", text: "All", label: "All slices" },
    ];

    /** B-scan lines per OCT, in the order the positions arrived. */
    const octs = $derived(
        Object.entries(
            localizer.locators().reduce<Record<string, number>>(
                (out, l) => ({
                    ...out,
                    [l.octImageId]: (out[l.octImageId] ?? 0) + 1,
                }),
                {},
            ),
        ),
    );
</script>

<LayerSection title="Localizer lines" {open} {ontoggle}>
    <div class="flex flex-col gap-1 px-4 py-2">
        <ToggleGroup
            label="Localizer lines"
            value={localizer.mode}
            onchange={(mode) => localizer.set(mode as LocalizerMode)}
            items={MODES}
            class="self-start"
        />
        <ul class="text-body-compact-01 text-text-primary">
            {#each octs as [octId, n] (octId)}
                <li>{octLabel(octId, n, win.twins.get(octId) ?? "")}</li>
            {/each}
        </ul>
    </div>
</LayerSection>
