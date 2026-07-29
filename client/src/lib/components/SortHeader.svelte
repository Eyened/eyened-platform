<script lang="ts">
    let { label, onclick }: { label: string; onclick: (e: unknown) => void } =
        $props();
</script>

<button class="inline-flex items-center gap-2 text-left font-medium" {onclick}>
    {label}
</button>
