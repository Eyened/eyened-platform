<script lang="ts">
    import Selection from "$lib/browser/Selection.svelte";
    import Toggle from "$lib/Toggle.svelte";
    import UserMenu from "$lib/UserMenu.svelte";
    import MainIcon from "$lib/viewer-window/icons/MainIcon.svelte";
    import { onMount, setContext } from "svelte";
    import Spinner from "../utils/Spinner.svelte";
    import BrowserContent from "./BrowserContent.svelte";
    import { BrowserContext, setParam } from "./browserContext.svelte";
    import FilterConditions from "./FilterConditions.svelte";
    import FilterImages from "./FilterImages.svelte";
    import FilterShorcuts from "./FilterShorcuts.svelte";
    import { globalContext } from "$lib/main";
    const { creator } = $globalContext;
    const initials = creator.name
        .split(" ")
        .map((name) => name[0])
        .join("");

    const browserContext = new BrowserContext([]);
    setContext("browserContext", browserContext);

    onMount(() => {
        browserContext.loadDataFromServer();
    });

    let renderMode = $state(true);

    function showUserMenu() {
        $globalContext.popupComponent = { component: UserMenu };
    }

    function search() {
        browserContext.loadDataFromServer();
    }

    async function loadMore(event) {
        await setParam("StudyDate~~>=", browserContext.next_cursor!);
        browserContext.loadDataFromServer();
    }
</script>

{#if browserContext.loading}
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
            </div>
            <div id="browser-header-right">
                <FilterImages />
                <FilterConditions />
                <button onclick={search} disabled={browserContext.no_params_set}>Search</button>
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
        <div class="display-toggle">
            Display:
            <Toggle
                bind:control={renderMode}
                textOn="studies"
                textOff="instances"
            />
            {#if browserContext.next_cursor}
                <div>
                    <!-- svelte-ignore a11y_click_events_have_key_events -->
                    <!-- svelte-ignore a11y_no_static_element_interactions -->
                    <span class="link" onclick={loadMore}
                        >Large result set, click to load more</span
                    >
                </div>
            {/if}
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
    div.display-toggle {
        display: flex;        
        padding: 1em;
        flex-direction: column;
    }
    span.link {
        cursor: pointer;
    }
    span.link:hover {
        text-decoration: underline;
    }
</style>
