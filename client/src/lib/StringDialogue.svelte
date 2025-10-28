<script lang="ts">
    import { Button } from "./components/ui/button/index.js";

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
    <Button variant="outline" onclick={_resolve}>{approve}</Button>
    <Button variant="outline" onclick={_reject}>{decline}</Button>
</div>
