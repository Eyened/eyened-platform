<script lang="ts">
    import type { Registration } from "$lib/registration/registration.svelte";
    import { AffineRegistration } from "$lib/registration/affine";
    import { Matrix } from "$lib/matrix";

    interface Props {
        registration: Registration;
        /** Stable identity — effect should run once per value, not loop on revision. */
        trigger: number;
        onRun?: () => void;
    }

    let { registration, trigger, onRun }: Props = $props();

    // Mirrors RegistrationItemLoader: $effect imports into Registration.
    // Before untrack-on-bump, revision++ subscribed this effect → infinite loop.
    $effect(() => {
        void trigger;
        onRun?.();
        registration.importRegistrationItems(
            [new AffineRegistration("a", "b_proj", Matrix.identity)],
            false,
        );
        registration.recomputePathsNow();
    });
</script>
