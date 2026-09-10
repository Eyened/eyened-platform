# Task panel in the grading window — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> Use the Cursor default model only. Do not switch to another model for subagents.

**Goal:** Replace the full-screen task overlay with a collapsible column on the right of the top-row thumbnails, configurable via `TaskConfig.task_panel`.

**Architecture:** Parse `task_panel` from `task.task_definition.config`. Persist expand/collapse in `localStorage` per task id. Render `TaskPanel` (refactor of `TaskOverlay`) between the thumbnail row and the Help/add-images icon strip. The overlay host keeps Help and Browser only.

**Tech Stack:** SvelteKit 5, Svelte 5 runes, Vitest + Testing Library, existing `updateSubTask` / `updateSubTaskComments` / `TaskNavigation`.

## Global Constraints

- Client-only: no API, OpenAPI, or ORM schema changes. `TaskConfig` stays untyped JSON on the wire.
- Nest all new knobs under `task_panel` so they coexist with `form_schema_name`, `form_image_scope`, and a future `layout` object.
- Do not merge or depend on `feat/dynamic-layout-from-taskconfig`.
- Do not add a MainViewer sidebar panel or a new `PanelName`.
- Keep `TaskNavigation` as full-page navigation (`window.location.href`).
- `TaskPanel` reads `taskContext.task.task_definition.config`, not `globalContext.config`.
- Status buttons: `aria-pressed={isActive}`. Do not copy `aria-current="isActive"`.
- Run all client commands from `client/` (`npm test`, `npm run check`, `npm run lint`).

---

## File structure

| Path | Responsibility |
|---|---|
| `client/src/lib/tasks/taskPanelConfig.ts` | Parse/merge `task_panel` from task-definition config |
| `client/src/lib/tasks/taskPanelConfig.test.ts` | Defaults, partial sections, bad types, unknown keys |
| `client/src/lib/tasks/taskPanelExpandedPrefs.ts` | `localStorage` get/set expanded flag per task id |
| `client/src/lib/tasks/taskPanelExpandedPrefs.test.ts` | Isolation, malformed JSON, storage throws |
| `client/src/lib/tasks/TaskPanel.svelte` | Column UI: collapse chrome + expanded comments/overview |
| `client/src/lib/tasks/TaskPanel.test.ts` | Section visibility, expand toggle, mocked APIs |
| `client/src/lib/viewer-window/TopRowImages.svelte` | Mount `TaskPanel`; drop overlay/task icons |
| Delete: `client/src/lib/tasks/TaskOverlay.svelte` | Replaced by `TaskPanel` |
| `client/eslint-suppressions.json` | Remove the `TaskOverlay.svelte` entry after delete |
| `docs/src/content/docs/orm/form_schemas.mdx` | Document `task_panel` on TaskConfig |
| `docs/src/content/docs/orm/data_model/tasks.mdx` | Short pointer |

Unchanged: `TaskContext.svelte.ts`, `taskUtils.svelte.ts`, `TaskMain.svelte`, `MainViewer.svelte`.

---

### Task 1: `parseTaskPanelConfig`

**Files:**
- Create: `client/src/lib/tasks/taskPanelConfig.ts`
- Test: `client/src/lib/tasks/taskPanelConfig.test.ts`

**Interfaces:**
- Consumes: `task.task_definition.config` as `unknown`
- Produces:

```ts
export type TaskPanelSections = {
    title: boolean;
    nav: boolean;
    status: boolean;
    comments: boolean;
    overview: boolean;
};

export type TaskPanelConfig = {
    enabled: boolean;
    expanded: boolean;
    sections: TaskPanelSections;
};

export function parseTaskPanelConfig(
    taskDefinitionConfig: unknown,
): TaskPanelConfig;
```

Defaults: `enabled: true`, `expanded: false`, every section `true`.

- [ ] **Step 1: Write the failing tests**

Create `client/src/lib/tasks/taskPanelConfig.test.ts`:

```ts
import { describe, it, expect } from "vitest";
import { parseTaskPanelConfig } from "./taskPanelConfig";

describe("parseTaskPanelConfig", () => {
    it("returns defaults when config is missing", () => {
        expect(parseTaskPanelConfig(undefined)).toEqual({
            enabled: true,
            expanded: false,
            sections: {
                title: true,
                nav: true,
                status: true,
                comments: true,
                overview: true,
            },
        });
    });

    it("returns defaults when task_panel is absent", () => {
        expect(
            parseTaskPanelConfig({ form_schema_name: "Naevi grading" }),
        ).toMatchObject({ enabled: true, expanded: false });
    });

    it("honors enabled false", () => {
        expect(parseTaskPanelConfig({ task_panel: { enabled: false } }).enabled).toBe(
            false,
        );
    });

    it("merges partial sections onto defaults", () => {
        const result = parseTaskPanelConfig({
            task_panel: { expanded: true, sections: { comments: false } },
        });
        expect(result.expanded).toBe(true);
        expect(result.sections.comments).toBe(false);
        expect(result.sections.status).toBe(true);
        expect(result.sections.overview).toBe(true);
    });

    it("ignores unknown keys and wrong types", () => {
        const result = parseTaskPanelConfig({
            task_panel: {
                expanded: "yes",
                extra: 1,
                sections: { comments: "no", title: true },
            },
        });
        expect(result.expanded).toBe(false);
        expect(result.sections.comments).toBe(true);
        expect(result.sections.title).toBe(true);
        expect(result).not.toHaveProperty("extra");
    });

    it("treats a non-object task_panel as missing", () => {
        expect(parseTaskPanelConfig({ task_panel: [] }).enabled).toBe(true);
    });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd client && npm test -- src/lib/tasks/taskPanelConfig.test.ts`

Expected: FAIL — cannot find module `./taskPanelConfig`

- [ ] **Step 3: Write the implementation**

Create `client/src/lib/tasks/taskPanelConfig.ts`:

```ts
export type TaskPanelSections = {
    title: boolean;
    nav: boolean;
    status: boolean;
    comments: boolean;
    overview: boolean;
};

export type TaskPanelConfig = {
    enabled: boolean;
    expanded: boolean;
    sections: TaskPanelSections;
};

const SECTION_KEYS = [
    "title",
    "nav",
    "status",
    "comments",
    "overview",
] as const;

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === "object" && value !== null && !Array.isArray(value);
}

function defaultConfig(): TaskPanelConfig {
    return {
        enabled: true,
        expanded: false,
        sections: {
            title: true,
            nav: true,
            status: true,
            comments: true,
            overview: true,
        },
    };
}

export function parseTaskPanelConfig(
    taskDefinitionConfig: unknown,
): TaskPanelConfig {
    const next = defaultConfig();
    if (!isRecord(taskDefinitionConfig)) return next;
    const raw = taskDefinitionConfig.task_panel;
    if (!isRecord(raw)) return next;

    if (typeof raw.enabled === "boolean") next.enabled = raw.enabled;
    if (typeof raw.expanded === "boolean") next.expanded = raw.expanded;

    if (isRecord(raw.sections)) {
        for (const key of SECTION_KEYS) {
            const value = raw.sections[key];
            if (typeof value === "boolean") next.sections[key] = value;
        }
    }

    return next;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd client && npm test -- src/lib/tasks/taskPanelConfig.test.ts`

Expected: PASS (all 6 tests)

- [ ] **Step 5: Commit**

```bash
git add -f client/src/lib/tasks/taskPanelConfig.ts client/src/lib/tasks/taskPanelConfig.test.ts
git commit -m "$(cat <<'EOF'
feat(client): parse TaskConfig.task_panel for the grading panel

EOF
)"
```

---

### Task 2: Expanded-state `localStorage` prefs

**Files:**
- Create: `client/src/lib/tasks/taskPanelExpandedPrefs.ts`
- Test: `client/src/lib/tasks/taskPanelExpandedPrefs.test.ts`

**Interfaces:**
- Consumes: `parseTaskPanelConfig(...).expanded` as the fallback boolean (caller passes it)
- Produces:

```ts
export const TASK_PANEL_EXPANDED_STORAGE_KEY = "eyened:taskPanelExpanded";

export function getTaskPanelExpanded(
    taskId: number,
    defaultValue: boolean,
): boolean;

export function setTaskPanelExpanded(
    taskId: number,
    expanded: boolean,
): void;
```

Map shape: `{ [taskId: string]: boolean }`. Fail-soft like `client/src/lib/viewer/imageUiPrefs.ts`.

- [ ] **Step 1: Write the failing tests**

Create `client/src/lib/tasks/taskPanelExpandedPrefs.test.ts`:

```ts
import { describe, it, expect, beforeEach, vi } from "vitest";
import {
    TASK_PANEL_EXPANDED_STORAGE_KEY,
    getTaskPanelExpanded,
    setTaskPanelExpanded,
} from "./taskPanelExpandedPrefs";

describe("taskPanelExpandedPrefs", () => {
    beforeEach(() => {
        localStorage.clear();
        vi.restoreAllMocks();
    });

    it("returns the default when nothing is stored", () => {
        expect(getTaskPanelExpanded(7, false)).toBe(false);
        expect(getTaskPanelExpanded(7, true)).toBe(true);
    });

    it("round-trips per task id", () => {
        setTaskPanelExpanded(1, true);
        setTaskPanelExpanded(2, false);
        expect(getTaskPanelExpanded(1, false)).toBe(true);
        expect(getTaskPanelExpanded(2, true)).toBe(false);
    });

    it("returns the default when JSON is malformed", () => {
        localStorage.setItem(TASK_PANEL_EXPANDED_STORAGE_KEY, "{not json");
        expect(getTaskPanelExpanded(1, false)).toBe(false);
    });

    it("returns the default when stored JSON is not an object", () => {
        localStorage.setItem(TASK_PANEL_EXPANDED_STORAGE_KEY, "[]");
        expect(getTaskPanelExpanded(1, true)).toBe(true);
    });

    it("does not throw when localStorage.setItem throws", () => {
        vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
            throw new Error("quota");
        });
        expect(() => setTaskPanelExpanded(1, true)).not.toThrow();
    });

    it("does not throw when localStorage.getItem throws", () => {
        vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
            throw new Error("blocked");
        });
        expect(getTaskPanelExpanded(1, false)).toBe(false);
    });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd client && npm test -- src/lib/tasks/taskPanelExpandedPrefs.test.ts`

Expected: FAIL — cannot find module `./taskPanelExpandedPrefs`

- [ ] **Step 3: Write the implementation**

Create `client/src/lib/tasks/taskPanelExpandedPrefs.ts`:

```ts
export const TASK_PANEL_EXPANDED_STORAGE_KEY = "eyened:taskPanelExpanded";

type ExpandedMap = Record<string, boolean>;

function canUseStorage(): boolean {
    return typeof localStorage !== "undefined";
}

function readAll(): ExpandedMap {
    if (!canUseStorage()) return {};
    try {
        const raw = localStorage.getItem(TASK_PANEL_EXPANDED_STORAGE_KEY);
        if (!raw) return {};
        const parsed: unknown = JSON.parse(raw);
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
            return {};
        }
        return parsed as ExpandedMap;
    } catch {
        return {};
    }
}

export function getTaskPanelExpanded(
    taskId: number,
    defaultValue: boolean,
): boolean {
    const value = readAll()[String(taskId)];
    return typeof value === "boolean" ? value : defaultValue;
}

export function setTaskPanelExpanded(taskId: number, expanded: boolean): void {
    if (!canUseStorage()) return;
    try {
        const all = readAll();
        all[String(taskId)] = expanded;
        localStorage.setItem(
            TASK_PANEL_EXPANDED_STORAGE_KEY,
            JSON.stringify(all),
        );
    } catch {
        // fail soft: in-memory toggle still works for this page load
    }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd client && npm test -- src/lib/tasks/taskPanelExpandedPrefs.test.ts`

Expected: PASS (all 6 tests)

- [ ] **Step 5: Commit**

```bash
git add -f client/src/lib/tasks/taskPanelExpandedPrefs.ts client/src/lib/tasks/taskPanelExpandedPrefs.test.ts
git commit -m "$(cat <<'EOF'
feat(client): persist task-panel expanded state per task

EOF
)"
```

---

### Task 3: `TaskPanel` component

**Files:**
- Create: `client/src/lib/tasks/TaskPanel.svelte`
- Test: `client/src/lib/tasks/TaskPanel.test.ts`

**Interfaces:**
- Consumes: `parseTaskPanelConfig` from Task 1; `getTaskPanelExpanded` / `setTaskPanelExpanded` from Task 2; `TaskContext` (`task`, `subTask`, `subTaskIndex`); `TaskNavigation`; `updateSubTask`; `updateSubTaskComments`
- Produces: Svelte component with prop `{ taskContext: TaskContext }`. Renders nothing when `enabled` is false. Collapsed: title `Set {subTaskIndex} of {task.num_tasks}`, prev/next, status. Expanded: those plus comments textarea and a "Task overview" button. Expand control `aria-label` is `"Expand task panel"` / `"Collapse task panel"`, hidden when both `comments` and `overview` are false.

- [ ] **Step 1: Write the failing tests**

Create `client/src/lib/tasks/TaskPanel.test.ts`:

```ts
import "@testing-library/jest-dom/vitest";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import TaskPanel from "./TaskPanel.svelte";
import type { TaskContext } from "./TaskContext.svelte";
import type { TaskGET, SubTaskWithImagesGET } from "../../types/openapi_types";
import { TASK_PANEL_EXPANDED_STORAGE_KEY } from "./taskPanelExpandedPrefs";

const updateSubTask = vi.fn().mockResolvedValue({});
const updateSubTaskComments = vi.fn().mockResolvedValue({});

vi.mock("$lib/data/api", () => ({
    updateSubTask: (...args: unknown[]) => updateSubTask(...args),
}));

vi.mock("$lib/data", () => ({
    updateSubTaskComments: (...args: unknown[]) =>
        updateSubTaskComments(...args),
}));

vi.mock("$app/state", () => ({
    page: { url: new URL("http://localhost/tasks/1/grade/0") },
}));

vi.mock("svelte-sonner", () => ({
    toast: { error: vi.fn() },
}));

function makeContext(
    config: unknown = {},
    overrides: Partial<TaskContext> = {},
): TaskContext {
    const task = {
        id: 42,
        name: "AMD",
        description: null,
        contact_id: null,
        task_definition_id: 1,
        date_inserted: "2026-01-01T00:00:00",
        num_tasks: 10,
        num_tasks_ready: 1,
        creator: null,
        task_state: null,
        task_definition: {
            id: 1,
            name: "Definition",
            config,
            date_inserted: "2026-01-01T00:00:00",
        },
        projects: null,
    } as TaskGET;
    const subTask = {
        id: 7,
        task_id: 42,
        task_index: 3,
        task_state: "NotStarted",
        comments: "hello",
        creator_id: null,
        images: [],
    } as unknown as SubTaskWithImagesGET;
    return { task, subTask, subTaskIndex: 3, ...overrides };
}

describe("TaskPanel", () => {
    beforeEach(() => {
        localStorage.clear();
        updateSubTask.mockClear();
        updateSubTaskComments.mockClear();
    });

    it("renders nothing when enabled is false", () => {
        render(TaskPanel, {
            props: {
                taskContext: makeContext({ task_panel: { enabled: false } }),
            },
        });
        expect(screen.queryByText("Set 3 of 10")).not.toBeInTheDocument();
    });

    it("shows collapsed chrome without comments or overview", () => {
        render(TaskPanel, { props: { taskContext: makeContext() } });
        expect(screen.getByText("Set 3 of 10")).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: "Previous subtask" }),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: "Next subtask" }),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: "NotStarted", pressed: true }),
        ).toBeInTheDocument();
        expect(
            screen.queryByPlaceholderText("Add comments..."),
        ).not.toBeInTheDocument();
        expect(
            screen.queryByRole("button", { name: "Task overview" }),
        ).not.toBeInTheDocument();
    });

    it("hides status when that section is off", () => {
        render(TaskPanel, {
            props: {
                taskContext: makeContext({
                    task_panel: { sections: { status: false } },
                }),
            },
        });
        expect(
            screen.queryByRole("button", { name: "NotStarted" }),
        ).not.toBeInTheDocument();
    });

    it("hides the expand control when comments and overview are off", () => {
        render(TaskPanel, {
            props: {
                taskContext: makeContext({
                    task_panel: {
                        sections: { comments: false, overview: false },
                    },
                }),
            },
        });
        expect(
            screen.queryByRole("button", { name: "Expand task panel" }),
        ).not.toBeInTheDocument();
        expect(
            screen.queryByRole("button", { name: "Collapse task panel" }),
        ).not.toBeInTheDocument();
    });

    it("reveals comments and overview when expanded", async () => {
        render(TaskPanel, { props: { taskContext: makeContext() } });
        await fireEvent.click(
            screen.getByRole("button", { name: "Expand task panel" }),
        );
        expect(
            screen.getByPlaceholderText("Add comments..."),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: "Task overview" }),
        ).toBeInTheDocument();
        expect(
            JSON.parse(
                localStorage.getItem(TASK_PANEL_EXPANDED_STORAGE_KEY) ?? "{}",
            ),
        ).toEqual({ "42": true });
    });

    it("starts expanded when localStorage says so", () => {
        localStorage.setItem(
            TASK_PANEL_EXPANDED_STORAGE_KEY,
            JSON.stringify({ "42": true }),
        );
        render(TaskPanel, { props: { taskContext: makeContext() } });
        expect(
            screen.getByPlaceholderText("Add comments..."),
        ).toBeInTheDocument();
    });

    it("calls updateSubTask when a status button is clicked", async () => {
        render(TaskPanel, { props: { taskContext: makeContext() } });
        await fireEvent.click(screen.getByRole("button", { name: "Busy" }));
        expect(updateSubTask).toHaveBeenCalledWith(7, { task_state: "Busy" });
    });

    it("calls updateSubTaskComments when comments change", async () => {
        localStorage.setItem(
            TASK_PANEL_EXPANDED_STORAGE_KEY,
            JSON.stringify({ "42": true }),
        );
        render(TaskPanel, { props: { taskContext: makeContext() } });
        const textarea = screen.getByPlaceholderText("Add comments...");
        await fireEvent.change(textarea, { target: { value: "updated" } });
        expect(updateSubTaskComments).toHaveBeenCalledWith(7, "updated");
    });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd client && npm test -- src/lib/tasks/TaskPanel.test.ts`

Expected: FAIL — cannot find module `./TaskPanel.svelte`

- [ ] **Step 3: Write `TaskPanel.svelte`**

Create `client/src/lib/tasks/TaskPanel.svelte`. This is a refactor of `TaskOverlay.svelte`: same actions, column layout, section flags, `aria-pressed`, toast on status failure. Use `{#each subTaskStates as state (state)}` so `svelte/require-each-key` is satisfied (do not add an eslint suppression).

```svelte
<script lang="ts">
    import { page } from "$app/state";
    import { ButtonGroup } from "$lib/components/ui/button-group";
    import Button from "$lib/components/ui/button/button.svelte";
    import { updateSubTaskComments } from "$lib/data";
    import { updateSubTask } from "$lib/data/api";
    import ChevronLeft from "@lucide/svelte/icons/chevron-left";
    import ChevronRight from "@lucide/svelte/icons/chevron-right";
    import { toast } from "svelte-sonner";
    import { subTaskStates } from "../../types/openapi_constants";
    import type { SubTaskState } from "../../types/openapi_types";
    import type { TaskContext } from "./TaskContext.svelte";
    import { parseTaskPanelConfig } from "./taskPanelConfig";
    import {
        getTaskPanelExpanded,
        setTaskPanelExpanded,
    } from "./taskPanelExpandedPrefs";
    import { TaskNavigation } from "./taskUtils.svelte";

    interface Props {
        taskContext: TaskContext;
    }

    let { taskContext }: Props = $props();

    const navigation = new TaskNavigation(taskContext);
    const subTask = $derived(taskContext.subTask);
    const task = $derived(taskContext.task);
    const subTaskIndex = $derived(taskContext.subTaskIndex);
    const panelConfig = $derived(
        parseTaskPanelConfig(task.task_definition.config),
    );
    const showExpandControl = $derived(
        panelConfig.sections.comments || panelConfig.sections.overview,
    );

    let expanded = $state(false);
    let isUpdatingState = $state(false);

    $effect(() => {
        expanded = getTaskPanelExpanded(task.id, panelConfig.expanded);
    });

    function toggleExpanded() {
        expanded = !expanded;
        setTaskPanelExpanded(task.id, expanded);
    }

    async function setState(state: SubTaskState) {
        isUpdatingState = true;
        try {
            await updateSubTask(subTask.id, { task_state: state });
        } catch (e) {
            toast.error(String(e));
        } finally {
            isUpdatingState = false;
        }
    }

    async function handleViewTask() {
        const suffix_string = `?${page.url.searchParams.toString()}`;
        const url = new URL(
            `${window.location.origin}/tasks/${task.id}${suffix_string}`,
        );
        window.location.href = url.href;
    }

    async function updateComments(comments: string) {
        try {
            await updateSubTaskComments(subTask.id, comments);
        } catch (e) {
            toast.error(String(e));
        }
    }
</script>

{#if panelConfig.enabled}
    <aside
        class="task-panel"
        class:expanded
        aria-label="Task"
    >
        {#if showExpandControl}
            <div class="controls">
                <Button
                    variant="outline"
                    size="sm"
                    onclick={toggleExpanded}
                    aria-expanded={expanded}
                    aria-label={expanded
                        ? "Collapse task panel"
                        : "Expand task panel"}
                >
                    {expanded ? "Collapse" : "Expand"}
                </Button>
            </div>
        {/if}

        {#if panelConfig.sections.title}
            <div class="title">Set {subTaskIndex} of {task.num_tasks}</div>
        {/if}

        {#if panelConfig.sections.nav}
            <div class="controls">
                <ButtonGroup orientation="vertical">
                    <Button
                        variant="outline"
                        size="sm"
                        onclick={() => navigation.prev()}
                        disabled={navigation.prevDisabled}
                        aria-label="Previous subtask"
                    >
                        <ChevronLeft />
                        Previous
                    </Button>
                    <Button
                        variant="outline"
                        size="sm"
                        onclick={() => navigation.next()}
                        disabled={navigation.nextDisabled}
                        aria-label="Next subtask"
                    >
                        Next
                        <ChevronRight />
                    </Button>
                </ButtonGroup>
            </div>
        {/if}

        {#if panelConfig.sections.status}
            <div class="controls">
                <div class:busy={isUpdatingState} aria-busy={isUpdatingState}>
                    <ButtonGroup orientation="vertical">
                        {#each subTaskStates as state (state)}
                            {@const isActive = subTask.task_state === state}
                            <Button
                                variant={isActive ? "default" : "outline"}
                                size="sm"
                                onclick={() => !isActive && setState(state)}
                                aria-pressed={isActive}
                                class={isActive ? "font-semibold" : ""}
                            >
                                {state}
                            </Button>
                        {/each}
                    </ButtonGroup>
                </div>
            </div>
        {/if}

        {#if expanded}
            {#if panelConfig.sections.comments}
                <div class="comments">
                    Comments:
                    <textarea
                        rows="6"
                        value={subTask.comments || ""}
                        onchange={async (e) => {
                            const target = e.target as HTMLTextAreaElement;
                            await updateComments(target.value);
                        }}
                        class="min-h-[60px] w-full rounded border p-2"
                        placeholder="Add comments..."
                    ></textarea>
                </div>
            {/if}

            {#if panelConfig.sections.overview}
                <div class="controls">
                    <Button variant="outline" onclick={handleViewTask}
                        >Task overview</Button
                    >
                </div>
            {/if}
        {/if}
    </aside>
{/if}

<style>
    aside.task-panel {
        display: flex;
        flex-direction: column;
        flex: 0 0 10rem;
        z-index: 2;
        background-color: black;
        color: rgba(255, 255, 255, 0.9);
        border-left: 1px solid rgba(255, 255, 255, 0.4);
        padding: 0.5rem;
        gap: 0.5rem;
        overflow-y: auto;
        overflow-x: hidden;
    }
    aside.task-panel.expanded {
        flex-basis: 18rem;
    }
    .title {
        font-weight: bold;
        font-size: 0.85rem;
        text-align: center;
    }
    .controls {
        display: flex;
        flex-direction: column;
        align-items: stretch;
    }
    .busy {
        opacity: 0.6;
        pointer-events: none;
        cursor: wait;
    }
    .comments {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        font-size: 0.85rem;
    }
    textarea {
        background-color: white;
        color: black;
    }
</style>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd client && npm test -- src/lib/tasks/TaskPanel.test.ts`

Expected: PASS (all 8 tests)

If `getByRole("button", { pressed: true })` fails because the Button primitive does not forward `aria-pressed`, set `aria-pressed={isActive ? "true" : undefined}` on the Button (still not `aria-current`). Re-run until green.

- [ ] **Step 5: Commit**

```bash
git add -f client/src/lib/tasks/TaskPanel.svelte client/src/lib/tasks/TaskPanel.test.ts
git commit -m "$(cat <<'EOF'
feat(client): add collapsible TaskPanel for grading chrome

EOF
)"
```

---

### Task 4: Wire `TopRowImages` and delete the overlay

**Files:**
- Modify: `client/src/lib/viewer-window/TopRowImages.svelte`
- Delete: `client/src/lib/tasks/TaskOverlay.svelte`
- Modify: `client/eslint-suppressions.json` — remove the `"src/lib/tasks/TaskOverlay.svelte"` key

**Interfaces:**
- Consumes: `TaskPanel` from Task 3 (`{ taskContext: TaskContext }`)
- Produces: Grade view shows `TaskPanel` to the right of thumbnails; Help (`?`) and add-images (`+`) remain; no full-screen task overlay; no prev/next/task icons in `#panel-selector`

- [ ] **Step 1: Replace task overlay wiring in `TopRowImages.svelte`**

In the `<script>` block:

- Remove imports: `TaskOverlay`, `TaskNavigation`, `ChevronLeft`, `ChevronRight`, `Task`
- Add: `import TaskPanel from "$lib/tasks/TaskPanel.svelte";`
- Remove `const navigation = new TaskNavigation(taskContext);`
- Change `let selectedPanel: "task" | "browser" | "help" | null` to `"browser" | "help" | null`
- Change `selectPanel`’s parameter type to match

In the markup, **between** `</div>` of `#images` and the `#panel` overlay, add:

```svelte
{#if taskContext}
    <TaskPanel {taskContext} />
{/if}
```

In `#panel`’s body, delete the `{#if selectedPanel == "task"}` branch (keep browser and help).

In `#panel-selector`, delete the `{#if taskContext}` block that renders prev/next/task icons. Leave:

```svelte
<div id="panel-selector">
    <div class="icon" onclick={() => selectPanel("help")}>?</div>
    <div class="icon" onclick={() => selectPanel("browser")}>+</div>
</div>
```

Do not add `task_panel` parsing here. `TaskPanel` hides itself when `enabled` is false.

- [ ] **Step 2: Delete `TaskOverlay.svelte` and its eslint suppression**

```bash
git rm client/src/lib/tasks/TaskOverlay.svelte
```

In `client/eslint-suppressions.json`, delete the entire `"src/lib/tasks/TaskOverlay.svelte"` object. Leave `"src/lib/viewer-window/TopRowImages.svelte"` (it still has `{#each}` without a key on instance/image loops).

- [ ] **Step 3: Run client tests and check**

Run:

```bash
cd client && npm test -- src/lib/tasks/ && npm run check
```

Expected: all `src/lib/tasks` tests PASS; `svelte-check` reports no errors from these files. If `check` fails on `selectedPanel == "task"` leftovers, remove them.

- [ ] **Step 4: Commit**

```bash
git add -f client/src/lib/viewer-window/TopRowImages.svelte client/eslint-suppressions.json
git commit -m "$(cat <<'EOF'
feat(client): show TaskPanel in the grading top row

Remove the full-screen task overlay and duplicate nav icons.

EOF
)"
```

(`git rm` of `TaskOverlay.svelte` is already staged from Step 2; include it in this commit if Step 2 did not commit.)

---

### Task 5: Document `task_panel` on TaskConfig

**Files:**
- Modify: `docs/src/content/docs/orm/form_schemas.mdx` (section “TaskConfig for grading tasks”)
- Modify: `docs/src/content/docs/orm/data_model/tasks.mdx` (TaskDefinition paragraph)

**Interfaces:**
- Consumes: the `TaskPanelConfig` shape from Task 1
- Produces: published docs that list `task_panel` next to `form_schema_name` / `form_image_scope`

- [ ] **Step 1: Update the example JSON and field table in `form_schemas.mdx`**

Replace the TaskConfig example with:

```json
{
  "form_schema_name": "Naevi grading",
  "form_image_scope": true,
  "task_panel": {
    "enabled": true,
    "expanded": false,
    "sections": {
      "title": true,
      "nav": true,
      "status": true,
      "comments": true,
      "overview": true
    }
  }
}
```

Add these rows to the field table (after `form_image_scope`):

| Field | Meaning |
|---|---|
| `task_panel.enabled` | When `false`, hide the grading task column. Default `true` |
| `task_panel.expanded` | Default expanded vs collapsed when the grader has no stored preference. Default `false` (collapsed) |
| `task_panel.sections.*` | Independently show `title`, `nav`, `status`, `comments`, `overview`. Each defaults to `true`. Missing `task_panel` means the panel is on with all sections, collapsed. Expand/collapse is stored in the browser per task |

- [ ] **Step 2: Point `tasks.mdx` at the same section**

Change the TaskDefinition paragraph from:

`TaskDefinitionName` and `TaskConfig` JSON — e.g. `form_schema_name` and `form_image_scope` for grading.

to:

`TaskDefinitionName` and `TaskConfig` JSON — e.g. `form_schema_name`, `form_image_scope`, and `task_panel` for the grading-window column. See **[Form schemas — TaskConfig](/eyened-platform/orm/form_schemas#taskconfig-for-grading-tasks)**.

- [ ] **Step 3: Commit**

```bash
git add docs/src/content/docs/orm/form_schemas.mdx docs/src/content/docs/orm/data_model/tasks.mdx
git commit -m "$(cat <<'EOF'
docs: document TaskConfig.task_panel for the grading column

EOF
)"
```

---

## Manual check (after Task 4)

On `/tasks/{id}/grade/{index}`:

1. Collapsed column is to the right of the top-row thumbnails: `Set N of M`, Previous/Next, NotStarted/Busy/Ready.
2. Help and `+` still open their overlays. Escape closes them. There is no task icon and no full-screen task overlay.
3. Expand shows comments and Task overview; Collapse hides them. Reload / prev / next keeps the choice for that task.
4. Clicking Ready patches status; the selected button follows the store.
5. A task definition with `"task_panel": { "enabled": false }` has no column; Help/`+` still work.
