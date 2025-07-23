<script lang="ts">
    import type { DataRow } from "$lib/utils/cached_source_loader";
    interface Props {
        data: DataRow[];
    }

    let { data }: Props = $props();
</script>

<div class="form-container">
    <table>
        <tbody>
            {#each data as row}
                <tr>
                    {#each row as cell}
                        <td>
                            {@html cell}
                        </td>
                    {/each}
                </tr>
            {/each}
        </tbody>
    </table>
</div>

<style>
    div.form-container {
        overflow: auto;
    }
    table {
        border-collapse: collapse;
        margin: 0 auto;
        font-size: small;
    }

    .light {
        table {
            color: rgb(2 9 65);
        }
        tr {
            &:nth-child(even) {
                background-color: rgb(248 250 252);
            }
            &:nth-child(odd) {
                background-color: rgb(241 245 249);
            }
            &:hover {
                background-color: rgb(226 232 240);
            }
            &:last-of-type {
                border-bottom: 2px solid rgb(2 9 65);
            }
        }
    }

    .dark {
        table {
            color: rgb(226 232 240);
        }
        tr {
            &:nth-child(even) {
                background-color: rgb(30 41 59);
            }
            &:nth-child(odd) {
                background-color: rgb(15 23 42);
            }
            &:hover {
                background-color: rgb(51 65 85);
            }
            &:last-of-type {
                border-bottom: 2px solid rgb(226 232 240);
            }
        }
    }

    td {
        padding-left: 1.5em;
        padding-right: 1.5em;
        &:nth-child(0) {
            text-align: center;
        }
        &:nth-child(3),
        &:nth-child(4) {
            text-align: end;
        }
    }
</style>
