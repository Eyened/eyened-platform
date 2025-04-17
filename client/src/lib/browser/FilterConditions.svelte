<script lang="ts">
    import type { Condition } from "$lib/types";
    import Icon from "$lib/gui/Icon.svelte";
    import { toggleParam } from "./searchUtils";
    import { page } from "$app/state";
    import { browser } from "$app/environment";

    const params = browser ? page.url.searchParams : new URLSearchParams();

    const conditions: Condition[] = [];
    for (const [key, value] of params) {
        if (key == "limit" || key == "page") continue;
        if (Array.isArray(value)) {
            for (const v of value) {
                conditions.push({ variable: key, operator: "=", value: v });
            }
        } else {
            conditions.push({ variable: key, operator: "=", value });
        }
    }

    function remove(condition: Condition) {
        toggleParam(params, condition.variable, condition.value);
        location.href = page.url.toString();
    }
</script>

<div id="main">
    <table>
        <tbody>
            {#each conditions as condition (condition)}
                <tr>
                    <td>{condition.variable}</td>
                    <td>{condition.operator}</td>
                    <td>{condition.value}</td>
                    <td
                        ><Icon
                            icon="delete"
                            type="tool"
                            onclick={() => remove(condition)}
                        /></td
                    >
                </tr>
            {/each}
        </tbody>
    </table>
</div>

<style>
    div#main {
        max-height: 5em;
        overflow: auto;
        border: 1px solid rgba(0, 0, 0, 0.1);
        border-radius: 2px;
        padding: 0.2em;
    }
    table {
        border-collapse: collapse;
        width: 100%;
    }
    td {
        padding: 0.2em;
    }
    tr:nth-child(odd) {
        background-color: rgba(255, 255, 255, 0.1);
    }

    tr:nth-child(even) {
        background-color: rgba(255, 255, 255, 0.2);
    }
</style>
