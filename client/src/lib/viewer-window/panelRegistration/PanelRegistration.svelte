<script lang="ts">
    import { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext } from "svelte";
    import { data } from "$lib/datamodel/model";
    import { ViewerWindowContext } from "../viewerWindowContext.svelte";
    import { FormAnnotation } from "$lib/datamodel/formAnnotation.svelte";
    import type { TaskContext } from "$lib/types";
    import RegistrationItem from "./RegistrationItem.svelte";
    import type { FormSchema } from "$lib/datamodel/formSchema.svelte";

    interface props {
        active: boolean;
        registrationSchema: FormSchema;
    }
    const { active, registrationSchema }: props = $props();

    const viewerContext = getContext<ViewerContext>("viewerContext");
    const taskContext = getContext<TaskContext>("taskContext");

    const { creator } = getContext<ViewerWindowContext>("viewerWindowContext");
    const {
        image: { instance },
    } = viewerContext;

    const { formAnnotations } = data;

    //filter all registrations for the same eye
    const filter = (formAnnotation: FormAnnotation) => {
        if (formAnnotation.formSchema !== registrationSchema) return false;
        if (formAnnotation.patient !== instance.patient) return false;
        if (formAnnotation.instance?.laterality !== instance.laterality)
            return false;
        return true;
    };
    const filtered = formAnnotations.filter(filter);

    async function create() {
        await FormAnnotation.createFrom(
            creator,
            instance,
            registrationSchema,
            taskContext?.subTask,
        );
    }

    class Activator {
        activeID: number | undefined = $state(undefined);
        toggle(formAnnotation: FormAnnotation) {
            if (this.activeID === formAnnotation.id) {
                this.activeID = undefined;
            } else {
                this.activeID = formAnnotation.id;
            }
        }
    }
    const activator = new Activator();
    // let activeId: null | number = $state(null);
    // function activate(formAnnotation: FormAnnotation) {
    // 	if (activeId === formAnnotation.id) {
    // 		activeId = null;
    // 	} else {
    // 		activeId = formAnnotation.id;
    // 	}
    // }
</script>

<div class="main">
    <div class="available">
        <ul>
            {#each $filtered.sort((a, b) => a.id - b.id) as formAnnotation (formAnnotation.id)}
                {#if formAnnotation.value != undefined}
                    <RegistrationItem {formAnnotation} {active} {activator} />
                {/if}
            {/each}
        </ul>
    </div>
    <div class="new">
        <button onclick={create}> Create new registration set </button>
    </div>
</div>

<style>
    div.main {
        padding: 0.5em;
        min-height: 0;
        flex: 1 1 auto;
        overflow-y: auto;
        min-height: 0px;
    }
    div.new,
    div.available {
        padding: 0.2em;
        margin-bottom: 0.5em;
    }
    ul {
        list-style-type: none;
        padding-inline-start: 0em;
    }
</style>
