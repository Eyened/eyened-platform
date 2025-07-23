<script lang="ts">
    interface Props {
        size?: string;
    }
    let { size = "2em" }: Props = $props();
</script>

<svg
    width={size}
    height={size}
    viewBox="0 0 64 64"
    xmlns="http://www.w3.org/2000/svg"
>
    <defs>
        <circle r="24" id="circle_left" cy="32" cx="24" />
        <circle r="24" id="circle_right" cy="32" cx="40" />
        <clipPath id="mask_left">
            <use xlink:href="#circle_right" />
        </clipPath>
    </defs>
    <g>
        <use
            xlink:href="#circle_left"
            id="center"
            fill="currentColor"
            fill-opacity="0.5"
            clip-path="url(#mask_left)"
        />
        <use xlink:href="#circle_left" stroke="currentColor" fill="none" />
        <use
            xlink:href="#circle_right"
            stroke="currentColor"
            fill-opacity="0.5"
            fill="currentColor"
        />
    </g>
</svg>

<style>
    svg {
        fill: none;
        stroke: currentColor;
    }
</style>
