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

<ConditionBuilder {properties} bind:rows={browserContext.advancedRows} />
