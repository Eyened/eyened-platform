<script lang="ts">
    import { page } from "$app/state";
    import { PanelIcon } from "$lib/viewer-window/icons/icons";
    import Trash from "$lib/viewer-window/icons/Trash.svelte";
    import { removeParam } from "./browserContext.svelte";
    
    
    class Condition {
        constructor(
            public readonly variable: string,
            public readonly operator: string,
            public readonly value: string,
        ) {}

        get key() {
            if (this.operator == "=") {
                return this.variable;
            }
            return `${this.variable}~~${this.operator}`;
        }
    }

    function getCondition(key: string, value: string): Condition {
        const parts = key.split("~~");
        let operator = "=";
        if (parts.length == 2) {
            operator = parts[1];
        } else if (parts.length > 2) {
            throw new Error(`Invalid condition: ${key}`);
        }
        return new Condition(parts[0], operator, value);
    }

    function remove(condition: Condition) {
        removeParam(condition.key, condition.value);
    }
</script>

{#snippet variable(variable: string, value: string)}
    {@const condition = getCondition(variable, value)}
    <div class="condition">
        <span>
            {condition.variable}
            {condition.operator}
            {condition.value}
        </span>
        <PanelIcon onclick={() => remove(condition)}>
            <Trash />
        </PanelIcon>
    </div>
{/snippet}

<div class="filter-conditions">
    {#each page.url.searchParams.entries() as [key, value]}
        {#if Array.isArray(value)}
            {#each value as v}
                {@render variable(key, v)}
            {/each}
        {:else}
            {@render variable(key, value)}
        {/if}
    {/each}
</div>

<style>
    .filter-conditions {
        display: flex;
        flex-direction: column;
        flex-wrap: wrap;
    }

    .condition {
        display: flex;
        align-items: center;
    }
    .condition:hover {
        background-color: rgba(0, 0, 0, 0.1);
        color: black;
    }
</style>
