<script lang="ts">
  let { label, onclick }: { label: string; onclick: (e: unknown) => void } = $props();
</script>

<button class="text-left font-medium inline-flex items-center gap-2" onclick={onclick}>
  {label}
</button>
