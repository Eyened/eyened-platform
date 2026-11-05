import { fireEvent, render, screen } from "@testing-library/svelte";
import { createRawSnippet } from "svelte";
import { describe, expect, it, vi } from "vitest";
import {
    expectNoAxeViolations,
    mockWidth,
    workspaceContext,
    workspaceWith,
} from "./testUtils";
import WorkspaceHeader, { type TaskHeader } from "./WorkspaceHeader.svelte";

function taskHeader(over: Partial<TaskHeader> = {}): TaskHeader {
    return {
        label: "Set 2 of 5",
        prevDisabled: false,
        nextDisabled: false,
        prev: vi.fn(),
        next: vi.fn(),
        overview: vi.fn(),
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
    it("shows no set navigation outside a task", () => {
        renderHeader(null);
        expect(screen.queryByRole("button", { name: "Next set" })).toBeNull();
        expect(screen.queryByText("Task overview")).toBeNull();
    });

    it("in a task, labels the set and wires Previous, Next and Task overview", async () => {
        const task = taskHeader();
        renderHeader(task);
        expect(screen.getByText("Set 2 of 5")).toBeInTheDocument();
        await fireEvent.click(
            screen.getByRole("button", { name: "Previous set" }),
        );
        await fireEvent.click(screen.getByRole("button", { name: "Next set" }));
        await fireEvent.click(
            screen.getByRole("button", { name: "Task overview" }),
        );
        expect(task.prev).toHaveBeenCalledTimes(1);
        expect(task.next).toHaveBeenCalledTimes(1);
        expect(task.overview).toHaveBeenCalledTimes(1);
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
            screen.queryByRole("button", {
                name: "Task overview",
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
});
