import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import { mockWidth, workspaceContext, workspaceWith } from "./testUtils";
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

function renderHeader(task: TaskHeader | null, narrow = false) {
    mockWidth({ md: true, xlg: true });
    return render(WorkspaceHeader, {
        props: { task, narrow },
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

    it("narrow: Task overview moves into the More menu", async () => {
        const task = taskHeader();
        renderHeader(task, true);
        const overview = screen.getByRole("button", {
            name: "Task overview",
            hidden: true,
        });
        expect(overview.closest("[hidden]")).not.toBeNull();
        await fireEvent.click(screen.getByRole("button", { name: "More" }));
        await fireEvent.click(
            screen.getByRole("button", { name: "Task overview" }),
        );
        expect(task.overview).toHaveBeenCalledTimes(1);
        expect(screen.getByRole("button", { name: "More" })).toHaveFocus();
    });
});
