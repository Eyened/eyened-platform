<script lang="ts">
    import * as Dialog from "$lib/components/ui/dialog/index.js";
    import { IconButton } from "$lib/components/ui/icon-button/index.js";
    import { modalSizeClasses } from "$lib/components/ui/modal/sizes.js";
    import { cn } from "$lib/utils.js";
    import { copyToClipboard } from "$lib/utils/copyToClipboard";
    import Copy from "carbon-icons-svelte/lib/Copy.svelte";
    import InstanceInfoLazy from "./InstanceInfoLazy.svelte";

    // An image's information: Carbon Modal lg, passive (the close button only; an outside click closes it), titled by the public ID with its copy.
    let {
        instanceId,
        open = $bindable(false),
    }: { instanceId: string; open?: boolean } = $props();

    let copied = $state(false);
    // Carbon CopyButton feedback: "Copied!" for 2 s.
    async function copy() {
        copied = await copyToClipboard(instanceId);
        setTimeout(() => (copied = false), 2000);
    }
</script>

<Dialog.Root bind:open>
    <Dialog.Content class={cn("gap-0 p-0", modalSizeClasses.lg)}>
        <Dialog.Header class="mb-2 pt-4 pr-12 pl-4">
            <p class="text-label-01 text-text-secondary">Image</p>
            <div class="flex min-w-0 items-center gap-2">
                <Dialog.Title class="truncate">{instanceId}</Dialog.Title>
                <IconButton
                    label={copied ? "Copied!" : "Copy public ID"}
                    closeOnClick={false}
                    onclick={copy}
                >
                    <Copy />
                </IconButton>
            </div>
        </Dialog.Header>
        <div
            class="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto px-4 pt-2 pb-12 md:overflow-hidden"
        >
            <InstanceInfoLazy {instanceId} />
        </div>
    </Dialog.Content>
</Dialog.Root>
