<script lang="ts">
    interface Props {
        size?: string;
    }
    let { size = "2em" }: Props = $props();
</script>

<svg
    xmlns="http://www.w3.org/2000/svg"
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
>
    <rect
        x="4"
        y="5"
        width="16"
        height="14"
        stroke="currentColor"
        stroke-width="2"
        stroke-dasharray="3 2"
    />
</svg>

<style>
    svg {
        stroke: none;
    }
</style>
