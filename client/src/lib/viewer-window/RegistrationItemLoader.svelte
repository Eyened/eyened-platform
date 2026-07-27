<script lang="ts">
    /**
     * Keeps `registration` in sync with patient attrs + form-annotation
     * transforms. Pointset / affine form annotations are applied *after*
     * patient attrs so the last edited pointset always overrides any
     * existing edge between the same image ids.
     */
    import { formAnnotations, formSchemas } from "$lib/data/stores.svelte";
    import { BUILTIN_VIEWER_FORM_SCHEMA_NAMES } from "$lib/config/builtinFormSchemas";
    import {
        getAffineTransforms,
        getPointsetRegistrations,
    } from "$lib/registration/pointsetRegistration";
    import type { Registration } from "$lib/registration/registration";
    import {
        getRegistrationSets,
        type RegistrationSet,
    } from "$lib/registration/registrationItem";

    interface Props {
        registration: Registration;
        registrationSet?: RegistrationSet[];
    }
    let { registration, registrationSet }: Props = $props();

    $effect(() => {
        // Track patient sets (new array identity when patients/instances change).
        const patientSets = registrationSet;

        // Track every builtin registration form_data so point edits re-run this.
        const formItems: { name: string; form_data: unknown }[] = [];
        for (const fa of formAnnotations.values()) {
            const schema = formSchemas.get(fa.form_schema_id);
            if (!schema || !fa.form_data) continue;
            if (
                schema.name ===
                    BUILTIN_VIEWER_FORM_SCHEMA_NAMES.POINTSET_REGISTRATION ||
                schema.name ===
                    BUILTIN_VIEWER_FORM_SCHEMA_NAMES.AFFINE_REGISTRATION ||
                schema.name ===
                    BUILTIN_VIEWER_FORM_SCHEMA_NAMES.REGISTRATION_SET
            ) {
                formItems.push({ name: schema.name, form_data: fa.form_data });
            }
        }

        if (patientSets?.length) {
            registration.importPatientRegistrationSets(patientSets);
        }

        for (const { name, form_data } of formItems) {
            if (
                name === BUILTIN_VIEWER_FORM_SCHEMA_NAMES.POINTSET_REGISTRATION
            ) {
                registration.importRegistrationItems(
                    getPointsetRegistrations(
                        form_data as {
                            [img_id: string]: ({
                                x: number;
                                y: number;
                                index?: number | null;
                            } | null)[];
                        },
                    ),
                );
            } else if (
                name === BUILTIN_VIEWER_FORM_SCHEMA_NAMES.AFFINE_REGISTRATION
            ) {
                registration.importRegistrationItems(
                    getAffineTransforms(form_data as any),
                );
            } else if (
                name === BUILTIN_VIEWER_FORM_SCHEMA_NAMES.REGISTRATION_SET
            ) {
                registration.importRegistrationItems(
                    getRegistrationSets(form_data as RegistrationSet[]),
                );
            }
        }

        registration.recomputePathsNow();
    });
</script>
