<script lang="ts">
    import { page } from "$app/state";
    import { PanelIcon } from "$lib/viewer-window/icons/icons";
    import Trash from "$lib/viewer-window/icons/Trash.svelte";
    import { removeParam } from "./browserContext.svelte";

    const operatorMap = {
        eq: "=",
        ne: "!=",
        gt: ">",
        lt: "<",
        gte: "≥",
        lte: "≤",
        in: "in",
        not_in: "not in",
        like: "like",
        ilike: "ilike",
        startswith: "startswith",
        endswith: "endswith",
        is_null: "is null",
        is_not_null: "is not null",
    };

    class Condition {
        constructor(
            public readonly variable: string,
            public readonly operator: string,
            public readonly value: string,
        ) {}

        get key() {
            if (this.operator == "eq") {
                return this.variable;
            }
            return `${this.variable}~~${this.operator}`;
        }

        get displayValue() {
            return `${this.variable} ${operatorMap[this.operator as keyof typeof operatorMap]} ${this.value}`;
        }
    }

    function getCondition(key: string, value: string): Condition {
        const parts = key.split("~~");
        let operator = "eq";
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
            {condition.displayValue}
        </span>
        <PanelIcon onclick={() => remove(condition)} theme="light">
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
        border-radius: 2px;
    }
    .condition:hover {
        background-color: var(--icon-hover);
        color: black;
    }
</style>
