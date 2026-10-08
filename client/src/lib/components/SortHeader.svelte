<script lang="ts">
    let { label, onclick }: { label: string; onclick: (e: unknown) => void } =
        $props();
</script>

<button class="font-medium inline-flex items-center gap-2 text-left" {onclick}>
    {label}
</button>
