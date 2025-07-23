<script lang="ts">
    interface Props {
        query: string;
        approve: string;
        decline: string;
        resolve: () => void;
        reject: () => void;
    }
    let { query, approve, decline, resolve, reject }: Props = $props();
</script>

<div class="dialogue-container">
    <div class="query">{query}</div>
    {#if approve}
        <button class="approve" onclick={resolve}>
            {approve}
        </button>
    {/if}
    {#if decline}
        <button class="decline" onclick={reject}>
            {decline}
        </button>
    {/if}
</div>

<style>
    div.buttons {
        flex: 1;
        justify-content: center;
    }
    button {
        margin: 0.2em;
    }
    .query {
        font-size: 20px;
        margin-bottom: 16px;
    }

    .approve,
    .decline {
        margin-top: 16px;
        padding: 8px 16px;
        border-radius: 1px;
        cursor: pointer;
    }
    .approve:hover,
    .decline:hover {
        background-color: aliceblue;
    }
</style>
