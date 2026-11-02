<script lang="ts">
    import { NativeSelectOption } from "$lib/components/ui/native-select/index.js";

    // Carbon SelectItem.
    let {
        value,
        text,
        disabled = false,
    }: { value: string; text: string; disabled?: boolean } = $props();
</script>

<NativeSelectOption {value} {disabled}>{text}</NativeSelectOption>
