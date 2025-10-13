<script lang="ts">
    import { formAnnotations, createFormAnnotation, instances } from '$lib/data';
    import type { FormSchemaGET } from '../../../types/openapi_types';
    import type { TaskContext } from '$lib/tasks/TaskContext.svelte';
    import { ViewerContext } from "$lib/viewer/viewerContext.svelte";
    import { getContext } from "svelte";
    import RegistrationItem from "./RegistrationItem.svelte";

    interface props {
        active: boolean;
        registrationSchema: FormSchemaGET;
    }
    const { active, registrationSchema }: props = $props();

    const viewerContext = getContext<ViewerContext>("viewerContext");
    const taskContext = getContext<TaskContext>("taskContext");

    const {
        image: { instance },
    } = viewerContext;

    //filter all registrations for the same eye
    const filtered = $derived(
        formAnnotations.filter(formAnnotation => {
                if (formAnnotation.form_schema_id !== registrationSchema.id) return false;
                if (formAnnotation.patient_id !== instance.patient.id) return false;
                // Check laterality - look up full instance if needed
                const formInstance = formAnnotation.image_instance_id 
                    ? instances.get(formAnnotation.image_instance_id)
                    : null;
                if (formInstance && formInstance.laterality !== instance.laterality) {
                    return false;
                }
                return true;
            })
            .sort((a, b) => a.id - b.id)
    );

    async function create() {
        await createFormAnnotation({
            form_schema_id: registrationSchema.id,
            patient_id: instance.patient.id,
            study_id: instance.study?.id ?? undefined,
            image_instance_id: instance.id,
            sub_task_id: taskContext?.subTask?.id,
            form_data: {},
        });
    }

    let activeID: number | undefined = $state(undefined);
    
</script>

<div class="main">
	<div class="available">
		<ul>
			{#each filtered as formAnnotation (formAnnotation.id)}
				<RegistrationItem {formAnnotation} {active} bind:activeID={activeID} />
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
