<script lang="ts">
    import { formSchemas } from "$lib/data/stores.svelte";
    import type { FormAnnotationGET } from "../../types/openapi_types";
    import {
        getAffineTransforms,
        getPointsetRegistrations,
    } from "$lib/registration/pointsetRegistration";
    import type { Registration } from "$lib/registration/registration";
    import { getRegistrationSets, type RegistrationSet } from "$lib/registration/registrationItem";

    interface Props {
        registration: Registration;
        formAnnotation?: FormAnnotationGET;
        registrationSet?: RegistrationSet[];
    }
    let { registration, formAnnotation, registrationSet }: Props = $props();

    const formSchema = $derived(
        formAnnotation ? formSchemas.get(formAnnotation.form_schema_id) : undefined
    );

    const updateFromFormAnnotation = (value: any) => {
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

    const updateFromPatientAttrs = (value: RegistrationSet[] | undefined) => {
        if (value?.length) {
            const items = getRegistrationSets(value);
            registration.importRegistrationItems(items);
        }
    };
    $effect(() => updateFromFormAnnotation(formAnnotation?.form_data));
    $effect(() => updateFromPatientAttrs(registrationSet));
</script>
