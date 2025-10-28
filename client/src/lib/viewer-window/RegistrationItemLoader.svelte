<script lang="ts">
    import { formSchemas } from "$lib/data/stores.svelte";
    import type { FormAnnotationGET } from "../../types/openapi_types";
    import {
        getAffineTransforms,
        getPointsetRegistrations,
    } from "$lib/registration/pointsetRegistration";
    import type { Registration } from "$lib/registration/registration";
    import { getRegistrationSets } from "$lib/registration/registrationItem";

    interface Props {
        registration: Registration;
        formAnnotation: FormAnnotationGET;
    }
    let { registration, formAnnotation }: Props = $props();

    const formSchema = $derived(formSchemas.get(formAnnotation.form_schema_id));

    const update = (value: any) => {
        if (value && formSchema) {
            if (formSchema.name === "Pointset registration") {
                const items = getPointsetRegistrations(value);
                registration.importRegistrationItems(items);
            } else if (formSchema.name === "Affine registration") {
                const items = getAffineTransforms(value);
                registration.importRegistrationItems(items);
            } else if (formSchema.name === "RegistrationSet") {
                const items = getRegistrationSets(value);
                registration.importRegistrationItems(items);
            }
        }
    };
    $effect(() => update(formAnnotation.form_data));
</script>
