<script lang="ts">
    export interface Props {
        query: string;
        approve: string;
        decline: string;
        close: () => void;
        resolve?: () => void;
        reject?: () => void;
    }
    let {
        query,
        approve,
        decline,
        close,
        resolve = () => {},
        reject = () => {},
    }: Props = $props();
    function _resolve() {
        resolve?.();
        close();
    }
    function _reject() {
        reject?.();
        close();
    }
</script>

<div>
    {query}
</div>

<div class="popup-footer">
    <button onclick={_resolve}>{approve}</button>
    <button onclick={_reject}>{decline}</button>
</div>
