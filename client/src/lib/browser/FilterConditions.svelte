<script lang="ts">
    import { searchParams } from "$lib/stores/searchParams";
    import type { Condition } from "$lib/types";

    function getCondition(variable: string): Condition {
        const params = new URLSearchParams(window.location.search);
        const value = params.get(variable) ?? '';
        return {
            variable: variable,
            operator: "=",
            value,
        };
    }

    function remove(condition: Condition) {
        searchParams.removeParam(condition.variable);
    }
</script>

<div class="filter-conditions">
    {#each Object.entries($searchParams) as [variable, value]}
        {@const condition = getCondition(variable)}
        <div class="condition">
            <span>{condition.variable} {condition.operator} {condition.value}</span>
            <button on:click={() => remove(condition)}>×</button>
        </div>
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
        align-items: left;        
        border-radius: 4px;
    }

    button {
        background: none;
        border: none;
        color: var(--color-text);
        cursor: pointer;
        padding: 0 0.25rem;
    }

    button:hover {
        color: var(--color-error);
    }
</style>
