import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import { workspaceContext, workspaceWith } from "$lib/workspace/testUtils";
import type { FormAnnotationGET } from "../../types/openapi_types";
import FormRow from "./FormRow.svelte";
import type { FormTarget } from "./formTargets";

const target = {
    key: "image:oct-1",
    scope: "ImageInstance",
    name: "OD · OCT · 2024-05-02",
    group: "OD · OCT · 2024-05-02",
    full: "OD · OCT · 2024-05-02 · Heidelberg Spectralis",
    imageIds: ["oct-1", "oct-1_proj"],
    ctx: { patientId: 1 },
    patientId: 1,
    patient: "P-0001",
} as FormTarget;

const form = {
    id: 9134,
    form_schema_id: 1,
    creator: { id: 8, name: "J. de Vries" },
    date_inserted: "2026-05-02T10:00:00",
    form_annotation_reference_id: 9020,
} as FormAnnotationGET;

function renderRow(props: Record<string, unknown>) {
    const ws = workspaceWith(1);
    render(FormRow, {
        props: {
            name: "OD · OCT · 2024-05-02",
            target,
            form,
            completion: "incomplete",
            open: false,
            current: false,
            depth: 1,
            canDelete: false,
            onopen: vi.fn(),
            oncopy: vi.fn(),
            ondelete: vi.fn(),
            ...props,
        },
        context: workspaceContext(ws),
    });
    return ws;
}

describe("FormRow", () => {
    it("the open form says so in its name, is the viewport's target and isn't a toggle", () => {
        renderRow({ open: true, current: true });
        const row = screen.getByRole("button", {
            name: "OD · OCT · 2024-05-02, not complete, in window",
        });
        expect(row).toHaveAttribute("aria-current", "true");
        expect(row).not.toHaveAttribute("aria-pressed");
    });

    it("a target without its form reads not graded, grade; the word Grade creates it too; no Copy or Delete", async () => {
        const onopen = vi.fn();
        renderRow({ form: null, completion: null, canDelete: true, onopen });
        expect(
            screen.getByRole("button", {
                name: "OD · OCT · 2024-05-02, not graded, grade",
            }),
        ).toBeInTheDocument();
        await fireEvent.click(screen.getByText("Grade"));
        expect(onopen).toHaveBeenCalledTimes(1);
        expect(screen.queryByRole("button", { name: "Copy" })).toBeNull();
        expect(
            screen.queryByRole("button", { name: "Delete form" }),
        ).toBeNull();
    });

    it("an Other forms row puts the date after the schema", () => {
        renderRow({ name: "DR severity", dated: true, completion: "complete" });
        expect(
            screen.getByRole("button", {
                name: "DR severity, 2026-05-02, complete",
            }),
        ).toBeInTheDocument();
    });

    it("hover and focus outline the target's images; leaving clears them", async () => {
        const ws = renderRow({});
        const row = screen
            .getByRole("button", { name: /^OD · OCT/ })
            .closest("[data-layer-row]")!;
        await fireEvent.pointerEnter(row);
        expect(ws.highlightedImages).toEqual(["oct-1", "oct-1_proj"]);
        await fireEvent.pointerLeave(row);
        expect(ws.highlightedImages).toEqual([]);
        await fireEvent.focusIn(row);
        expect(ws.highlightedImages).toEqual(["oct-1", "oct-1_proj"]);
        await fireEvent.focusOut(row);
        expect(ws.highlightedImages).toEqual([]);
    });

    it("Copy ignores the second click of a double-click, not a single click", async () => {
        const oncopy = vi.fn();
        renderRow({ oncopy });
        const copy = screen.getByRole("button", { name: "Copy" });
        await fireEvent.click(copy, { detail: 2 });
        expect(oncopy).not.toHaveBeenCalled();
        await fireEvent.click(copy, { detail: 1 });
        expect(oncopy).toHaveBeenCalledTimes(1);
    });

    it("Delete form ignores the second click of a double-click, not a single click", async () => {
        const ondelete = vi.fn();
        renderRow({ canDelete: true, ondelete });
        const del = screen.getByRole("button", { name: "Delete form" });
        await fireEvent.click(del, { detail: 2 });
        expect(ondelete).not.toHaveBeenCalled();
        await fireEvent.click(del, { detail: 1 });
        expect(ondelete).toHaveBeenCalledTimes(1);
    });
});
