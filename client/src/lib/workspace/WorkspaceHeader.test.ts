import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { createRawSnippet } from "svelte";
import { describe, expect, it, vi } from "vitest";
import type { ResolvedPathname } from "$app/types";
import {
    expectNoAxeViolations,
    mockWidth,
    workspaceContext,
    workspaceWith,
} from "./testUtils";
import { DebouncedSaver } from "$lib/saving/debouncedSaver.svelte";
import { saveTracker } from "$lib/saving/saveTracker.svelte";
import WorkspaceHeader, { type TaskHeader } from "./WorkspaceHeader.svelte";

function taskHeader(over: Partial<TaskHeader> = {}): TaskHeader {
    return {
        label: "Set 2 of 5",
        show: { title: true, nav: true, overview: true },
        pending: null,
        prevDisabled: false,
        nextDisabled: false,
        prev: vi.fn(),
        next: vi.fn(),
        overviewHref: "/tasks/7" as ResolvedPathname,
        ...over,
    };
}

const start = createRawSnippet(() => ({
    render: () => `<button type="button">Show menu</button>`,
}));
const end = createRawSnippet(() => ({
    render: () => `<button type="button">Show Layers and Grading</button>`,
}));

function renderHeader(task: TaskHeader | null, narrow = false) {
    mockWidth({ md: !narrow, xlg: !narrow });
    return render(WorkspaceHeader, {
        props: { task, narrow, start, end },
        context: workspaceContext(workspaceWith(2)),
    });
}

describe("WorkspaceHeader", () => {
    it("below md, a hidden live region says what couldn't save", async () => {
        const saver = new DebouncedSaver<number>({
            kind: "form",
            group: "form-annotation-1",
            target: { to: "focus", focus: () => {} },
            delay: 0,
            send: () => Promise.reject(new Error("offline")),
        });
        try {
            saver.edit(1);
            await saver.flush();
            renderHeader(taskHeader(), true);
            expect(
                document.querySelector(
                    '[data-header-slot="save-state"] [role="status"]',
                ),
            ).toHaveTextContent("1 form couldn't save");
        } finally {
            // The tracker is page-wide; leave it clean for the next test.
            saver.discard();
            saver.dispose();
            saveTracker.edited = false;
        }
    });

    it("shows no set navigation outside a task", () => {
        renderHeader(null);
        expect(screen.queryByRole("button", { name: "Next set" })).toBeNull();
        expect(screen.queryByText("Task overview")).toBeNull();
        expect(screen.queryByText("Show menu")).toBeNull();
    });

    it("in a task, labels the set and wires Previous and Next", async () => {
        const task = taskHeader();
        renderHeader(task);
        expect(screen.getByText("Set 2 of 5")).toBeInTheDocument();
        await fireEvent.click(
            screen.getByRole("button", { name: "Previous set" }),
        );
        await fireEvent.click(screen.getByRole("button", { name: "Next set" }));
        expect(task.prev).toHaveBeenCalledTimes(1);
        expect(task.next).toHaveBeenCalledTimes(1);
    });

    it("disables Previous on the first set and Next on the last", () => {
        renderHeader(taskHeader({ prevDisabled: true, nextDisabled: true }));
        const prev = screen.getByRole("button", { name: "Previous set" });
        const next = screen.getByRole("button", { name: "Next set" });
        expect(prev).toBeDisabled();
        expect(next).toBeDisabled();
    });

    it("narrow: drops the name, Task overview, Layout, More and the word Set, and puts the frame's controls first and last", async () => {
        const { container } = renderHeader(taskHeader(), true);
        expect(screen.queryByText("EyeNED")).toBeNull();
        expect(
            screen.queryByRole("link", {
                name: "Task overview, opens in a new tab",
                hidden: true,
            }),
        ).toBeNull();
        expect(screen.queryByRole("button", { name: "Layout" })).toBeNull();
        expect(screen.queryByRole("button", { name: "More" })).toBeNull();
        const buttons = screen.getAllByRole("button");
        expect(buttons[0]).toHaveTextContent("Show menu");
        expect(buttons.at(-1)).toHaveTextContent("Show Layers and Grading");
        expect(screen.getByText("2 of 5")).toHaveAttribute(
            "aria-hidden",
            "true",
        );
        expect(screen.getByText("Set 2 of 5")).toHaveClass("sr-only");
        await expectNoAxeViolations(container);
    });

    it("outside a task, Browse | All tools sets the palette's mode and remembers it; a task shows none", async () => {
        mockWidth({ md: true, xlg: true });
        const ws = workspaceWith(2);
        render(WorkspaceHeader, {
            props: { task: null, narrow: false },
            context: workspaceContext(ws),
        });
        await fireEvent.click(screen.getByRole("tab", { name: "Browse" }));
        expect(ws.toolMode).toBe("browse");
        expect(localStorage.getItem("eyened:viewer:toolMode")).toBe("browse");
        cleanup();
        renderHeader(taskHeader());
        expect(screen.queryByRole("tablist", { name: "Mode" })).toBeNull();
    });

    it("from md to lg: no product name, the short set label, Task overview and Layout as icons", () => {
        mockWidth({ md: true, lg: false, xlg: false });
        render(WorkspaceHeader, {
            props: { task: taskHeader(), narrow: false, start, end },
            context: workspaceContext(workspaceWith(2)),
        });
        expect(screen.queryByText("EyeNED")).toBeNull();
        expect(screen.getByText("Set 2 of 5")).toHaveClass("sr-only");
        expect(
            screen.getByRole("link", {
                name: "Task overview, opens in a new tab",
            }),
        ).not.toHaveTextContent("Task overview");
        expect(
            screen.getByRole("button", { name: "Layout" }),
        ).not.toHaveTextContent("Layout");
    });
});
