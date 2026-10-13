<script lang="ts">
    import { DatePicker } from "$lib/components/ui/date-picker/index.js";
    import { Dropdown } from "$lib/components/ui/dropdown/index.js";
    import { TextInput } from "$lib/components/ui/text-input/index.js";
    import { getContext } from "svelte";
    import type { BrowserContext } from "./browserContext.svelte";

    // Basic filters: each filled field is its own condition (AND, B10). Enter in a field submits
    // the surrounding search form.
    const ALL = "__all__";
    const browserContext = getContext<BrowserContext>("browserContext");
    let {
        patientInput = $bindable(null),
    }: { patientInput?: HTMLInputElement | null } = $props();

    const projectItems = $derived([
        { id: ALL, text: "All projects" },
        ...browserContext
            .getValueOptions("Project Name")
            .map((p) => ({ id: p, text: p })),
    ]);
</script>

<div class="grid gap-x-4 gap-y-6 md:grid-cols-3">
    <TextInput
        labelText="Patient identifier"
        autocomplete="off"
        bind:value={browserContext.basic.patientIdentifier}
        bind:ref={patientInput}
    />
    <DatePicker
        labelText="Study date"
        bind:value={browserContext.basic.studyDate}
    />
    <Dropdown
        labelText="Project"
        items={projectItems}
        bind:selectedId={
            () => browserContext.basic.projectName || ALL,
            (id) => (browserContext.basic.projectName = id === ALL ? "" : id)
        }
    />
</div>
