<!--
@component
Plugs today's viewer into the workspace frame: sets the viewer-window context,
loads registrations, renders MainViewer per viewport and StripViewer per strip tile, and hosts the Add images overlay.
-->
<script lang="ts">
    import { resolve } from "$app/paths";
    import FormsPanel from "$lib/forms/FormsPanel.svelte";
    import {
        formAnnotations,
        formSchemas,
        formSchemasByName,
    } from "$lib/data/stores.svelte";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import {
        incompleteForms,
        matchForms,
        openImages,
    } from "$lib/forms/formTargets";
    import { taskFormName } from "$lib/forms/taskForm";
    import IncompleteFormsModal from "$lib/tasks/IncompleteFormsModal.svelte";
    import { instances, patients } from "$lib/data";
    import type { RegistrationSet } from "$lib/registration/registrationItem";
    import { collectPatientRegistrationSets } from "$lib/registration/registrationItem";
    import { updateSubTask } from "$lib/data/api";
    import { updateSubTaskComments } from "$lib/data/helpers";
    import { COMMENTS_ID } from "$lib/forms/CommentsField.svelte";
    import { DebouncedSaver } from "$lib/saving/debouncedSaver.svelte";
    import { saveTracker } from "$lib/saving/saveTracker.svelte";
    import LeaveSetModal from "$lib/tasks/LeaveSetModal.svelte";
    import SetStatusControl from "$lib/tasks/SetStatusControl.svelte";
    import SetStatusTag from "$lib/tasks/SetStatusTag.svelte";
    import {
        parseTaskPanelConfig,
        taskHeaderShows,
    } from "$lib/tasks/taskPanelConfig";
    import type { TaskContext } from "$lib/tasks/TaskContext.svelte";
    import { takeHandoff } from "$lib/tasks/setHandoff";
    import {
        focusSetControl,
        SetNavigation,
    } from "$lib/tasks/setNavigation.svelte";
    import {
        navigateSubtaskIndex,
        TaskNavigation,
    } from "$lib/tasks/taskUtils.svelte";
    import { viewportTitle } from "$lib/workspace/imageMeta";
    import WorkspaceFrame from "$lib/workspace/WorkspaceFrame.svelte";
    import type { TaskHeader } from "$lib/workspace/WorkspaceHeader.svelte";
    import type { Workspace } from "$lib/workspace/workspace.svelte";
    import { getContext, onMount, setContext } from "svelte";
    import BrowserOverlay from "./BrowserOverlay.svelte";
    import MainViewer from "./MainViewer.svelte";
    import RegistrationItemLoader from "./RegistrationItemLoader.svelte";
    import StripViewer from "./StripViewer.svelte";
    import type { ViewerWindowContext } from "./viewerWindowContext.svelte";
    import type { SubTaskState } from "../../types/openapi_types";

    interface Props {
        viewerWindowContext: ViewerWindowContext;
    }

    let { viewerWindowContext }: Props = $props();
    setContext("viewerWindowContext", viewerWindowContext);
    const registration = viewerWindowContext.registration;

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
    const workspace = getContext<Workspace>("workspace");
    const globalContext = getContext<GlobalContext>("globalContext");
    const navigation = taskContext ? new TaskNavigation(taskContext) : null;
    // subTaskIndex is 0-based; people read sets from 1.
    const setNumber = (taskContext?.subTaskIndex ?? 0) + 1;
    const lastSet = taskContext
        ? taskContext.subTaskIndex >= taskContext.task.num_tasks - 1
        : false;
    // The set's status saves like any other edit, so ◀ ▶ wait for it.
    const statusSaver = taskContext
        ? new DebouncedSaver<SubTaskState>({
              kind: "status",
              group: "status",
              target: {
                  to: "grading",
                  footer: true,
                  focus: () => focusSetControl("status"),
              },
              delay: 0,
              send: (state) =>
                  updateSubTask(taskContext.subTask.id, { task_state: state }),
          })
        : null;
    const setNavigation =
        taskContext && statusSaver
            ? new SetNavigation({
                  tracker: saveTracker,
                  status: statusSaver,
                  index: taskContext.subTaskIndex,
                  count: taskContext.task.num_tasks,
                  navigate: navigateSubtaskIndex,
                  handoff: () => ({
                      selected: workspace.selected,
                      maximised: workspace.maximised,
                  }),
                  focus: focusSetControl,
                  // Read from the stores, so it works with Grading hidden or the column folded.
                  incomplete: () => {
                      const name = taskFormName(
                          taskContext.task.task_definition.config,
                      );
                      const userId = globalContext.user.id;
                      return incompleteForms(
                          matchForms({
                              forms: formAnnotations.values(),
                              images: openImages(
                                  workspace.catalogue,
                                  viewerWindowContext.images,
                              ),
                              schemas: formSchemas,
                              taskSchemaId: name
                                  ? formSchemasByName.get(name)?.id
                                  : undefined,
                              userId,
                              subTaskId: taskContext.subTask.id,
                          }),
                          formSchemas,
                          userId,
                          taskContext.subTask.id,
                      );
                  },
              })
            : null;
    const shows = taskContext
        ? taskHeaderShows(
              parseTaskPanelConfig(taskContext.task.task_definition.config),
          )
        : null;
    // The comments outlive the panel's markup, so their saver lives with the page, like the status saver.
    const commentsSaver =
        taskContext && shows?.comments
            ? new DebouncedSaver<string>({
                  kind: "comments",
                  group: "comments",
                  target: {
                      to: "grading",
                      focus: () =>
                          document.getElementById(COMMENTS_ID)?.focus(),
                  },
                  delay: 500,
                  send: (text) =>
                      updateSubTaskComments(taskContext.subTask.id, text),
              })
            : null;
    const task: TaskHeader | null = $derived(
        taskContext && navigation && setNavigation && shows
            ? {
                  label: `Set ${setNumber} of ${taskContext.task.num_tasks}`,
                  show: shows,
                  prevDisabled: navigation.prevDisabled,
                  nextDisabled: navigation.nextDisabled,
                  pending: setNavigation.pending,
                  prev: () =>
                      void setNavigation.move("prev", { markReady: false }),
                  next: () =>
                      void setNavigation.move("next", { markReady: false }),
                  overviewHref: resolve("/tasks/[taskid]", {
                      taskid: String(taskContext.task.id),
                  }),
                  tag: shows.status ? statusTag : undefined,
                  // With Status off the last set has no move, so nothing to show.
                  status:
                      shows.status || (shows.goToNext && !lastSet)
                          ? setStatus
                          : undefined,
                  notice: setNavigation.lastReady
                      ? {
                            title: `Set ${setNumber} marked ready`,
                            subtitle: "This was the last set in this task.",
                        }
                      : null,
              }
            : null,
    );

    // The control that left the last set keeps focus here: ▶ when ◀ can't take it.
    onMount(() => {
        const control = takeHandoff()?.control;
        if (!control || !navigation) return;
        focusSetControl(
            control === "prev" && navigation.prevDisabled ? "next" : control,
        );
    });

    let browserOpen = $state(false);

    function titleFor(imageId: string) {
        const image = viewerWindowContext.images.get(imageId);
        return image
            ? {
                  ...viewportTitle(image.instance),
                  twin: viewerWindowContext.twins.get(imageId) ?? "",
              }
            : null;
    }
</script>

{#snippet statusTag()}
    {#if taskContext}
        <SetStatusTag subTaskId={taskContext.subTask.id} />
    {/if}
{/snippet}

{#snippet setStatus()}
    {#if taskContext && setNavigation && statusSaver && shows}
        <SetStatusControl
            subTaskId={taskContext.subTask.id}
            index={taskContext.subTaskIndex}
            count={taskContext.task.num_tasks}
            showStatus={shows.status}
            navigation={setNavigation}
            status={statusSaver}
        />
    {/if}
{/snippet}

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
    {#snippet forms()}
        <FormsPanel comments={commentsSaver} />
    {/snippet}
</WorkspaceFrame>

{#if setNavigation?.question}
    <LeaveSetModal
        {setNumber}
        markReady={setNavigation.question.markReady}
        onanswer={(leave) => setNavigation.answerLeave(leave)}
    />
{/if}

{#if setNavigation?.readyQuestion}
    <IncompleteFormsModal
        {setNumber}
        lines={setNavigation.readyQuestion}
        last={lastSet}
        onanswer={(go) => setNavigation.answerReady(go)}
    />
{/if}

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
