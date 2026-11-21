<!--
@component
Display › Registration · OD / OS: the registration every viewport of this eye uses for Blend and the points it shows. Selecting a pointset never changes it.
-->
<script lang="ts">
    import { Dropdown } from "$lib/components/ui/dropdown/index.js";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext } from "svelte";
    import LayerSection from "./LayerSection.svelte";
    import { eyeKey, eyeRegistrationRows, eyeSuffix } from "./pointsets";

    let { open, ontoggle }: { open: boolean; ontoggle: () => void } = $props();

    const NONE = "none";
    const globalContext = getContext<GlobalContext>("globalContext");
    const viewerContext = getContext<ViewerContext>("viewerContext");
    const { instance } = viewerContext.image;
    const pointsets = viewerContext.viewerWindowContext.pointsets;
    const eye = eyeKey(instance);
    const title = `Registration${eyeSuffix(instance.laterality)}`;
    const inUseId = $derived(pointsets.currentId(eye));
    const rows = $derived(eyeRegistrationRows(instance, inUseId));
</script>

<LayerSection {title} {open} {ontoggle}>
    <div class="px-4 py-2">
        <Dropdown
            labelText={title}
            hideLabel
            size="sm"
            items={[
                { id: NONE, text: "None" },
                ...rows.map((r) => ({
                    id: String(r.id),
                    text: `Registration [${r.id}]`,
                    hint:
                        r.creator.id === globalContext.user.id
                            ? "Mine"
                            : r.creator.name,
                })),
            ]}
            selectedId={inUseId === undefined ? NONE : String(inUseId)}
            onselect={(id) =>
                pointsets.setCurrent(eye, id === NONE ? undefined : Number(id))}
        />
    </div>
</LayerSection>
