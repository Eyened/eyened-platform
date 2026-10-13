<script lang="ts">
    import { ConditionBuilder } from "$lib/components/ui/condition-builder/index.js";
    import { getContext } from "svelte";
    import type { BrowserContext } from "./browserContext.svelte";
    import { builderProperties } from "./conditionConfig";

    const browserContext = getContext<BrowserContext>("browserContext");
    const properties = $derived(
        builderProperties(browserContext.activeSignature),
    );
</script>

<div class="flex flex-col gap-2">
    <!-- The builder's grid is named by label; this is the visible copy. -->
    <p aria-hidden="true" class="text-label-01 text-text-secondary">
        Conditions
    </p>
    <ConditionBuilder
        {properties}
        label="Conditions"
        bind:rows={browserContext.advancedRows}
    />
</div>
