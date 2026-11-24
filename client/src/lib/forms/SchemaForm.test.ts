import { fireEvent, render, screen, within } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import SchemaForm from "./SchemaForm.svelte";
import type { JSONSchema } from "./schemaType";

const schema = {
    type: "object",
    required: ["grade"],
    properties: {
        grade: { description: "Grade", enum: ["A", "B", "C"] },
        count: { description: "Count", type: "integer" },
        seen: { description: "Seen", type: "boolean" },
        note: { description: "Note", type: "string" },
    },
} as JSONSchema;

function renderForm(props: Record<string, unknown> = {}) {
    const onchange = vi.fn();
    const view = render(SchemaForm, {
        props: { schema, value: {}, onchange, ...props },
    });
    return { onchange, ...view };
}

describe("SchemaForm", () => {
    it("keeps a missing answer calm until focus leaves the question, named by its legend", async () => {
        renderForm();
        const group = screen.getByRole("group", { name: "Grade (required)" });
        const [a, b] = within(group).getAllByRole("radio");
        await fireEvent.focusOut(a!, { relatedTarget: b });
        expect(screen.queryByText("Answer this question.")).toBeNull();
        await fireEvent.focusOut(b!, {
            relatedTarget: screen.getByLabelText("Note"),
        });
        expect(screen.getByText("Answer this question.")).toBeInTheDocument();
    });

    it("saves no answer while a whole-number question shows 2.7, and none for an emptied one", async () => {
        const { onchange } = renderForm({ value: { grade: "A", count: 3 } });
        const count = screen.getByLabelText("Count");
        await fireEvent.input(count, { target: { value: "2.7" } });
        expect(onchange).toHaveBeenLastCalledWith({ grade: "A" });
        await fireEvent.focusOut(count);
        expect(screen.getByText("Enter a whole number.")).toBeInTheDocument();
        await fireEvent.input(count, { target: { value: "5" } });
        expect(onchange).toHaveBeenLastCalledWith({ grade: "A", count: 5 });
        await fireEvent.input(count, { target: { value: "" } });
        expect(onchange).toHaveBeenLastCalledWith({ grade: "A" });
    });

    it("asks a yes/no question with Yes and No", async () => {
        const { onchange } = renderForm();
        await fireEvent.click(screen.getByRole("radio", { name: "Yes" }));
        expect(onchange).toHaveBeenLastCalledWith({ seen: true });
    });

    it("clears an answer with ×", async () => {
        const { onchange } = renderForm({ value: { grade: "B" } });
        await fireEvent.click(
            screen.getByRole("button", { name: "Clear answer: Grade" }),
        );
        expect(onchange).toHaveBeenLastCalledWith({});
    });

    it("shows someone else's form read-only, without Clear", () => {
        renderForm({ value: { grade: "B", note: "x" }, canEdit: false });
        expect(
            screen.queryByRole("button", { name: /Clear answer/ }),
        ).toBeNull();
        expect(screen.getByLabelText("Note")).toHaveAttribute("readonly");
    });

    it("after a Mark ready attempt, shows every question's error without a touch", () => {
        const twoRequired = {
            type: "object",
            required: ["grade", "note"],
            properties: {
                grade: { description: "Grade", enum: ["A", "B"] },
                note: { description: "Note", type: "string" },
            },
        } as JSONSchema;
        renderForm({ schema: twoRequired, markReadyAttempted: true });
        expect(screen.getAllByText("Answer this question.")).toHaveLength(2);
    });

    it("marks a question a condition makes required, while the condition holds", () => {
        const conditional = {
            type: "object",
            properties: {
                grade: { description: "Grade", enum: ["absent", "present"] },
                severity: { description: "Severity", enum: ["mild", "severe"] },
            },
            allOf: [
                {
                    if: {
                        properties: { grade: { const: "present" } },
                        required: ["grade"],
                    },
                    then: { required: ["severity"] },
                },
            ],
        } as unknown as JSONSchema;
        const first = renderForm({
            schema: conditional,
            value: { grade: "present" },
        });
        expect(
            screen.getByRole("group", { name: "Severity (required)" }),
        ).toBeInTheDocument();
        first.unmount();
        renderForm({ schema: conditional, value: { grade: "absent" } });
        expect(
            screen.getByRole("group", { name: "Severity" }),
        ).toBeInTheDocument();
    });

    it("hides an empty ruled-out question and flags one that still holds an answer", () => {
        const conditional = {
            type: "object",
            properties: {
                seen: { description: "Seen", type: "boolean" },
                note: { description: "Note", type: "string" },
            },
            allOf: [
                {
                    if: {
                        properties: { seen: { const: false } },
                        required: ["seen"],
                    },
                    then: { properties: { note: false } },
                },
            ],
        } as unknown as JSONSchema;
        const first = renderForm({
            schema: conditional,
            value: { seen: false },
        });
        expect(screen.queryByLabelText("Note")).toBeNull();
        first.unmount();
        renderForm({ schema: conditional, value: { seen: false, note: "x" } });
        expect(
            screen.getByText(
                "This question doesn't apply any more. Clear the answer.",
            ),
        ).toBeInTheDocument();
    });

    it("says how many answers a folded section misses", async () => {
        const sections = {
            type: "object",
            properties: {
                eye: {
                    type: "object",
                    description: "Left eye",
                    required: ["a", "b"],
                    properties: {
                        a: { description: "A", type: "string" },
                        b: { description: "B", type: "string" },
                    },
                },
            },
        } as JSONSchema;
        renderForm({ schema: sections, value: { eye: {} } });
        const trigger = screen.getByRole("button", { name: /Left eye/ });
        expect(trigger).not.toHaveTextContent("not answered");
        await fireEvent.click(trigger);
        expect(trigger).toHaveTextContent("2 not answered");
    });

    it("keeps focus in a list's text row while typing", async () => {
        const list = {
            type: "object",
            properties: {
                notes: {
                    type: "array",
                    description: "Notes",
                    items: { type: "string", description: "Note" },
                },
            },
        } as JSONSchema;
        const { onchange, rerender } = renderForm({
            schema: list,
            value: { notes: ["a"] },
        });
        const row = screen.getByLabelText("Note 1");
        row.focus();
        await fireEvent.input(row, { target: { value: "ab" } });
        expect(onchange).toHaveBeenLastCalledWith({ notes: ["ab"] });
        await rerender({ value: { notes: ["ab"] } });
        expect(screen.getByLabelText("Note 1")).toBe(row);
        expect(row).toHaveFocus();
    });

    it("keeps 2.7 in a whole-number list entry when the saved null comes back", async () => {
        const list = {
            type: "object",
            properties: {
                nums: {
                    type: "array",
                    description: "Counts",
                    items: { type: "integer" },
                },
            },
        } as JSONSchema;
        const { onchange, rerender } = renderForm({
            schema: list,
            value: { nums: [3] },
        });
        const box = screen.getByRole("spinbutton") as HTMLInputElement;
        await fireEvent.input(box, { target: { value: "2.7" } });
        await fireEvent.focusOut(box);
        await rerender({ value: onchange.mock.lastCall![0] });
        expect((screen.getByRole("spinbutton") as HTMLInputElement).value).toBe(
            "2.7",
        );
        expect(screen.getByText("Enter a whole number.")).toBeInTheDocument();
    });

    it("deletes an empty entry at once and asks before deleting one with answers", async () => {
        const group = {
            type: "object",
            properties: {
                naevi: {
                    type: "array",
                    description: "Naevi",
                    items: {
                        type: "object",
                        description: "Naevus",
                        properties: {
                            size: { description: "Size", type: "number" },
                        },
                    },
                },
            },
        } as JSONSchema;
        const { onchange } = renderForm({
            schema: group,
            value: { naevi: [{ size: 1 }, { size: 2 }, {}] },
        });
        await fireEvent.click(
            screen.getByRole("button", { name: "Delete Naevus 3" }),
        );
        expect(onchange).toHaveBeenLastCalledWith({
            naevi: [{ size: 1 }, { size: 2 }],
        });
        await fireEvent.click(
            screen.getByRole("button", { name: "Delete Naevus 2" }),
        );
        const dialog = await screen.findByRole("dialog", {
            name: "Delete Naevus 2",
        });
        expect(onchange).toHaveBeenCalledTimes(1);
        await fireEvent.click(
            within(dialog).getByRole("button", { name: "Delete" }),
        );
        await vi.waitFor(() =>
            expect(onchange).toHaveBeenLastCalledWith({
                naevi: [{ size: 1 }, {}],
            }),
        );
    });

    it("keeps an emptied list entry in its place", async () => {
        const lists = {
            type: "object",
            properties: {
                notes: {
                    type: "array",
                    description: "Notes",
                    items: { type: "string", description: "Note" },
                },
                sizes: {
                    type: "array",
                    description: "Sizes",
                    items: { type: "number", description: "Size" },
                },
            },
        } as JSONSchema;
        const { onchange } = renderForm({
            schema: lists,
            value: { notes: ["a", "b"], sizes: [1, 2] },
        });
        await fireEvent.input(screen.getByLabelText("Note 1"), {
            target: { value: "" },
        });
        expect(onchange).toHaveBeenLastCalledWith({
            notes: ["", "b"],
            sizes: [1, 2],
        });
        await fireEvent.input(screen.getByLabelText("Size 1"), {
            target: { value: "" },
        });
        expect(onchange).toHaveBeenLastCalledWith({
            notes: ["a", "b"],
            sizes: [null, 2],
        });
    });

    it("after a Mark ready attempt, names each missing answer with a link", () => {
        const twoRequired = {
            type: "object",
            required: ["grade", "note"],
            properties: {
                grade: { description: "Grade", enum: ["A", "B"] },
                note: { description: "Note", type: "string" },
            },
        } as JSONSchema;
        renderForm({ schema: twoRequired, markReadyAttempted: true });
        // The status line announces the notice title; the notice shows it too.
        expect(screen.getByRole("status")).toHaveTextContent(
            "2 required questions aren't answered",
        );
        expect(
            screen.getByRole("button", { name: "Grade" }),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: "Note" }),
        ).toBeInTheDocument();
    });
});
