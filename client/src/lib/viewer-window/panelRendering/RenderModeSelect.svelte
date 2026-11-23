<script lang="ts">
    import {
        getAvailableRenderModes,
        type RenderMode,
    } from "$lib/viewer/viewer-utils";

    interface Props {
        value: RenderMode;
        supportsColor: boolean;
        radio?: boolean;
        label?: string;
    }

    let {
        value = $bindable(),
        supportsColor,
        radio = false,
        label = "Render mode",
    }: Props = $props();

    const labels: Record<RenderMode, string> = {
        Original: "O<u>r</u>iginal",
        "Contrast enhanced": "Contrast <u>e</u>nhanced",
        "Color balanced": "Color <u>b</u>alanced",
        CLAHE: "CLA<u>H</u>E",
        Sharpened: "<u>S</u>harpened",
        "Histogram matched": "Histogram <u>m</u>atched",
        Luminance: "<u>L</u>uminance",
        Red: "Red",
        Green: "Green",
        Blue: "Blue",
    };

    const modes = $derived(getAvailableRenderModes(supportsColor));

    // Drop modes that are not available for this image (e.g. after switching)
    $effect(() => {
        if (!modes.includes(value)) {
            value = "Original";
        }
    });
</script>

{#if radio}
    <ul role="radiogroup" aria-label={label}>
        {#each modes as option (option)}
            <li>
                <label>
                    <input type="radio" bind:group={value} value={option} />
                    <!-- eslint-disable-next-line svelte/no-at-html-tags -- trusted, non-user content -->
                    {@html labels[option]}
                </label>
            </li>
        {/each}
    </ul>
{:else}
    <select bind:value aria-label={label}>
        {#each modes as option (option)}
            <option value={option}>{option}</option>
        {/each}
    </select>
{/if}

<style>
    ul {
        list-style-type: none;
        padding: 0;
    }
    label {
        white-space: nowrap;
    }
    label:hover {
        color: white;
    }
</style>
