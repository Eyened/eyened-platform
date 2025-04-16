<script lang="ts">
	import type { FormAnnotation } from '$lib/datamodel/formAnnotation';
	import {
		getAffineTransforms,
		getPointsetRegistrations
	} from '$lib/registration/pointsetRegistration';
	import type { Registration } from '$lib/registration/registration';
	import { getRegistrationSets } from '$lib/registration/registrationItem';
	import { onDestroy } from 'svelte';

	interface Props {
		registration: Registration;
		formAnnotation: FormAnnotation;
	}
	let { registration, formAnnotation }: Props = $props();

	const update = (value: any) => {
		if (value) {
			if (formAnnotation.formSchema.name === 'Pointset registration') {
				const items = getPointsetRegistrations(value);
				registration.importRegistrationItems(items);
			} else if (formAnnotation.formSchema.name === 'Affine registration') {
				const items = getAffineTransforms(value);
				registration.importRegistrationItems(items);
			} else if (formAnnotation.formSchema.name === 'RegistrationSet') {
				const items = getRegistrationSets(value);
				registration.importRegistrationItems(items);
			}
		}
	};
	onDestroy(formAnnotation.value.subscribe(update));
	formAnnotation.value.load();
</script>
