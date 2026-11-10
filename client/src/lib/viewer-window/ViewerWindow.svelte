<!--
@component
Plugs today's viewer into the workspace frame: sets the viewer-window context,
loads registrations, renders MainViewer per viewport and StripViewer per strip tile, and hosts the Add images overlay.
-->
<script lang="ts">
    import { instances, patients } from "$lib/data";
    import type { RegistrationSet } from "$lib/registration/registrationItem";
    import { collectPatientRegistrationSets } from "$lib/registration/registrationItem";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import { TaskNavigation } from "$lib/tasks/taskUtils.svelte";
    import { viewportTitle } from "$lib/workspace/imageMeta";
    import WorkspaceFrame from "$lib/workspace/WorkspaceFrame.svelte";
    import type { TaskHeader } from "$lib/workspace/WorkspaceHeader.svelte";
    import type { Workspace } from "$lib/workspace/workspace.svelte";
    import { getContext, setContext } from "svelte";
    import BrowserOverlay from "./BrowserOverlay.svelte";
    import MainViewer from "./MainViewer.svelte";
    import RegistrationItemLoader from "./RegistrationItemLoader.svelte";
    import StripViewer from "./StripViewer.svelte";
    import type { ViewerWindowContext } from "./viewerWindowContext.svelte";

    interface Props {
        viewerWindowContext: ViewerWindowContext;
    }

    let { viewerWindowContext }: Props = $props();
    setContext("viewerWindowContext", viewerWindowContext);
    const registration = viewerWindowContext.registration;
    const workspace = getContext<Workspace>("workspace");
    // The Localizer lines setting shows only when some open image has B-scan positions.
    $effect(() => {
        workspace.hasLocalizers = viewerWindowContext.photoLocators.size > 0;
    });

    let registrationSet: RegistrationSet[] = $derived.by(() => {
        const result: RegistrationSet[] = [];
        const patientIds = new Set<number>(
            viewerWindowContext.instanceIds
                .map((id) => instances.get(id)?.patient.id)
                .filter((pid): pid is number => typeof pid === "number"),
        );
        for (const patientId of patientIds) {
            const patient = patients.get(patientId);
            result.push(...collectPatientRegistrationSets(patient?.attrs));
        }
        return result;
    });

    const taskContext = getContext<TaskContext | undefined>("taskContext");
    const navigation = taskContext ? new TaskNavigation(taskContext) : null;
    // subTaskIndex is 0-based: TaskNavigation disables Previous at 0.
    const task: TaskHeader | null = $derived(
        taskContext && navigation
            ? {
                  label: `Set ${taskContext.subTaskIndex} of ${taskContext.task.num_tasks}`,
                  prevDisabled: navigation.prevDisabled,
                  nextDisabled: navigation.nextDisabled,
                  prev: () => navigation.prev(),
                  next: () => navigation.next(),
                  overview: () => {
                      window.location.href = `/tasks/${taskContext.task.id}`;
                  },
              }
            : null,
    );

    let browserOpen = $state(false);

    function titleFor(imageId: string) {
        const image = viewerWindowContext.images.get(imageId);
        return image ? viewportTitle(image.instance) : null;
    }
</script>

<!-- Patient attrs first, then form pointset/affine (pointset wins on conflict). -->
<RegistrationItemLoader {registration} {registrationSet} />

<WorkspaceFrame
    {titleFor}
    {task}
    onaddimages={() => (browserOpen = true)}
    emptyMessage={viewerWindowContext.instanceIds.length === 0
        ? "Enter instance IDs in url"
        : null}
>
    {#snippet viewer(imageId: string)}
        {@const image = viewerWindowContext.images.get(imageId)}
        {#if image}
            <MainViewer {image} />
        {/if}
    {/snippet}
    {#snippet tile(imageId: string)}
        {@const image = viewerWindowContext.images.get(imageId)}
        {#if image}
            <StripViewer {image} />
        {/if}
    {/snippet}
</WorkspaceFrame>

{#if browserOpen}
    <!-- isolate keeps the overlay's z-index below menus portalled to <body>. -->
    <div class="isolate">
        <div
            class="fixed inset-0 z-1000 flex flex-col overflow-hidden bg-background text-text-primary"
            role="dialog"
            aria-modal="true"
            aria-label="Add images"
            tabindex="-1"
            onkeydown={(e) => {
                if (e.key === "Escape") browserOpen = false;
            }}
        >
            <BrowserOverlay
                {viewerWindowContext}
                onClose={() => (browserOpen = false)}
            />
        </div>
    </div>
{/if}
