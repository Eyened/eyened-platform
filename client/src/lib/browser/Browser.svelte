<script lang="ts">
    import { goto } from "$app/navigation";
    import { getContext, onMount, setContext } from "svelte";
    import { type GlobalContext } from "$lib/data-loading/globalContext.svelte";
    import { loadSearchParams } from "$lib/datamodel/api";
    import Selection from "$lib/browser/Selection.svelte";
    import Toggle from "$lib/Toggle.svelte";
    import MainIcon from "$lib/viewer-window/icons/MainIcon.svelte";
    import Spinner from "../utils/Spinner.svelte";
    import BrowserContent from "./BrowserContent.svelte";
    import FilterConditions from "./FilterConditions.svelte";
    import QuickFilter from "./FilterImages.svelte";
    import FilterShorcuts from "./FilterShorcuts.svelte";
    import UserMenu from "$lib/UserMenu.svelte";
    import { BrowserContext } from "./browserContext.svelte";
    import { page } from "$app/state";
    import { data } from "$lib/datamodel/model";
    import { browser } from "$app/environment";

    let loading = $state(false);

    const globalContext = getContext<GlobalContext>("globalContext");
    const creator = globalContext.creator;
    const initials = creator.name
        .split(" ")
        .map((name) => name[0])
        .join("");

    const { instances } = data;
    const browserContext = new BrowserContext(instances, []);
    setContext("browserContext", browserContext);

    async function loadDataFromServer() {
        if (!browser) {
            return;
        }
        const params = page.url.searchParams;
        if (!params.has("limit")) {
            params.set("limit", "200");
        }
        if (!params.has("page")) {
            params.set("page", "0");
        }
        goto("?" + params.toString());

        const validVariables = [
            "PatientIdentifier",
            "StudyDate",
            "StudyDate~~>=",
            "StudyDate~~=<",
            "ProjectName",
            "FeatureName",
            "CreatorName",
            "Modality",
            "ManufacturerModelName",
        ];
        let isValid = false;
        for (const key of validVariables) {
            if (params.has(key)) {
                isValid = true;
                break;
            }
        }
        if (!isValid) {
            console.warn("search params are not valid", params.toString());
            return;
        }

        loading = true;
        await loadSearchParams(params);
        loading = false;
    }

    onMount(loadDataFromServer);

    let renderMode = $state(true);

    function showUserMenu() {
        globalContext.popupComponent = { component: UserMenu };
    }
</script>

{#if loading}
    <div class="loader">
        <div>
            <Spinner />
        </div>
    </div>
{/if}
<div id="container">
    <div id="main">
        <div id="browser-header">
            <div id="browser-header-left">
                <FilterShorcuts />
                <QuickFilter />
            </div>
            <div id="browser-header-right">
                <FilterConditions />
            </div>
            <div id="user">
                <MainIcon
                    onclick={showUserMenu}
                    tooltip={creator.name}
                    style="light"
                >
                    {#snippet icon()}
                        <span class="icon">{initials}</span>
                    {/snippet}
                </MainIcon>
            </div>
        </div>
        <div>
            Display:
            <Toggle
                bind:control={renderMode}
                textOn="studies"
                textOff="instances"
            />
        </div>
    </div>

    <div id="content">
        <BrowserContent renderMode={renderMode ? "studies" : "instances"} />
    </div>

    <div id="selection">
        <Selection />
    </div>
</div>

<style>
    .loader {
        height: 100vh;
        width: 100vw;
        position: fixed; /* Stay in place */
        z-index: 1; /* Sit on top */
        left: 0;
        top: 0;
        background-color: rgba(255, 255, 255, 0.7); /* Black w/opacity */
        backdrop-filter: blur(5px); /* Filter effect */
    }
    .loader > div {
        position: absolute;
        left: 50%;
        top: 50%;
        transform: translate(-50%, -50%);
    }
    div#browser-header {
        display: flex;
    }
    div#browser-header {
        flex: 1;
    }

    div#container {
        height: 100vh;
        display: flex;
        flex-direction: column;
        overflow: hidden;
    }
    div#container > div {
        flex: 0;
    }
    div#container > div#content {
        padding: 1em;
        overflow-y: auto;
        flex: 1;
    }
    div#main {
        flex: 1;
        background-color: #d7d7d7;
        font-size: 0.8em;
        border-bottom: 3px solid #f1f1f1;
    }
    div#browser-header-left,
    div#browser-header-right {
        flex: 1;
        padding: 1em;
    }
    div#user {
        flex: 0;
        padding: 1em;
    }

    div#selection {
        flex: 0;
    }

    span.icon {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0.2em;
        width: 2em;
        height: 2em;
        margin: auto;
        border: 1px solid rgba(255, 255, 255, 0.5);
        border-radius: 50%;
        font-weight: bold;
    }
    span.icon:hover {
        background-color: rgba(178, 229, 253, 0.5);
    }
</style>
