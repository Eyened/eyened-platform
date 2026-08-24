<script lang="ts">
    import { formSchemas } from "$lib/data/stores.svelte";
    import type { FormAnnotationGET } from "../../types/openapi_types";
    import {
        getAffineTransforms,
        getPointsetRegistrations,
    } from "$lib/registration/pointsetRegistration";
    import type { Registration } from "$lib/registration/registration";
    import { getRegistrationSets, type RegistrationSet } from "$lib/registration/registrationItem";
    import { BUILTIN_VIEWER_FORM_SCHEMA_NAMES } from "$lib/config/builtinFormSchemas";

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
            if (formSchema.name === BUILTIN_VIEWER_FORM_SCHEMA_NAMES.POINTSET_REGISTRATION) {
                const items = getPointsetRegistrations(value);
                registration.importRegistrationItems(items);
                registration.recomputePathsNow();
            } else if (formSchema.name === BUILTIN_VIEWER_FORM_SCHEMA_NAMES.AFFINE_REGISTRATION) {
                const items = getAffineTransforms(value);
                registration.importRegistrationItems(items);
                registration.recomputePathsNow();
            } else if (formSchema.name === BUILTIN_VIEWER_FORM_SCHEMA_NAMES.REGISTRATION_SET) {
                const items = getRegistrationSets(value);
                registration.importRegistrationItems(items);
                registration.recomputePathsNow();
            }
        }
    };

    const updateFromPatientAttrs = (value: RegistrationSet[] | undefined) => {
        if (value?.length) {
            registration.importPatientRegistrationSets(value);
        }
    };
    $effect(() => updateFromFormAnnotation(formAnnotation?.form_data));
    $effect(() => updateFromPatientAttrs(registrationSet));
</script>
