import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import PointRowEditor from "./PointRowEditor.svelte";

/** Opens a Dropdown trigger and picks the option starting with `text`. */
async function pick(trigger: HTMLElement, text: string) {
    trigger.focus();
    await fireEvent.keyDown(trigger, { key: "Enter" });
    const option = (await screen.findAllByRole("option")).find((o) =>
        o.textContent?.trim().startsWith(text),
    )!;
    await fireEvent.pointerDown(option, { button: 0, pointerType: "mouse" });
    await fireEvent.pointerUp(option, { button: 0, pointerType: "mouse" });
}

const row = {
    publicId: "img1",
    index: 0,
    pt: { x: 10.4, y: 20.6, index: 3, severity: "mild", note: "fovea" },
};

describe("PointRowEditor", () => {
    it("edits coordinates, extras, and remove", async () => {
        const onUpdateCoord = vi.fn();
        const onUpdateExtra = vi.fn();
        const onRemove = vi.fn();
        const onCollapse = vi.fn();

        render(PointRowEditor, {
            props: {
                row,
                canEdit: true,
                hasExtras: true,
                enumExtras: [{ key: "severity", values: ["mild", "severe"] }],
                stringExtraKeys: ["note"],
                indexApplicable: () => true,
                allowNullIndex: true,
                number: 1,
                onUpdateCoord,
                onUpdateExtra,
                onRemove,
                onCollapse,
            },
        });

        expect(screen.getByText("Point 1")).toBeInTheDocument();

        const x = screen.getByLabelText("x") as HTMLInputElement;
        await fireEvent.input(x, { target: { value: "15" } });
        expect(onUpdateCoord).toHaveBeenCalledWith("img1", 0, "x", "15");

        const y = screen.getByLabelText("y") as HTMLInputElement;
        await fireEvent.input(y, { target: { value: "25" } });
        expect(onUpdateCoord).toHaveBeenCalledWith("img1", 0, "y", "25");

        const i = screen.getByLabelText("B-scan") as HTMLInputElement;
        await fireEvent.input(i, { target: { value: "" } });
        expect(onUpdateCoord).toHaveBeenCalledWith("img1", 0, "index", "");

        const trigger = screen.getByLabelText("severity");
        expect(trigger).toHaveTextContent("mild");
        await pick(trigger, "severe");
        expect(onUpdateExtra).toHaveBeenCalledWith(
            "img1",
            0,
            "severity",
            "severe",
        );

        const note = screen.getByDisplayValue("fovea") as HTMLInputElement;
        await fireEvent.input(note, { target: { value: "disc" } });
        expect(onUpdateExtra).toHaveBeenCalledWith("img1", 0, "note", "disc");

        await fireEvent.click(
            screen.getByRole("button", { name: "Delete point" }),
        );
        expect(onRemove).toHaveBeenCalled();

        await fireEvent.click(screen.getByRole("button", { name: "Done" }));
        expect(onCollapse).toHaveBeenCalled();
    });

    it("omits None when the enum is required", async () => {
        render(PointRowEditor, {
            props: {
                row,
                number: 1,
                canEdit: true,
                hasExtras: true,
                enumExtras: [
                    {
                        key: "severity",
                        values: ["mild", "severe"],
                        required: true,
                    },
                ],
                stringExtraKeys: [],
                indexApplicable: () => false,
                onUpdateCoord: vi.fn(),
                onUpdateExtra: vi.fn(),
                onRemove: vi.fn(),
                onCollapse: vi.fn(),
            },
        });

        const trigger = screen.getByLabelText("severity");
        trigger.focus();
        await fireEvent.keyDown(trigger, { key: "Enter" });
        const names = (await screen.findAllByRole("option")).map((o) =>
            o.textContent?.trim(),
        );
        expect(names).toEqual(["mild", "severe"]);
    });

    it("shows no grade when a required one is missing, and saves the pick", async () => {
        const onUpdateExtra = vi.fn();
        render(PointRowEditor, {
            props: {
                row: { publicId: "img1", index: 0, pt: { x: 10, y: 20 } },
                number: 1,
                canEdit: true,
                hasExtras: true,
                enumExtras: [
                    {
                        key: "severity",
                        values: ["mild", "severe"],
                        required: true,
                    },
                ],
                stringExtraKeys: [],
                indexApplicable: () => false,
                onUpdateCoord: vi.fn(),
                onUpdateExtra,
                onRemove: vi.fn(),
                onCollapse: vi.fn(),
            },
        });

        const trigger = screen.getByLabelText("severity");
        expect(trigger).toHaveTextContent("Choose an option");
        await pick(trigger, "mild");
        expect(onUpdateExtra).toHaveBeenCalledWith(
            "img1",
            0,
            "severity",
            "mild",
        );
    });

    it("hides edit controls when read-only", () => {
        render(PointRowEditor, {
            props: {
                row: { publicId: "img1", index: 0, pt: { x: 1, y: 2 } },
                canEdit: false,
                hasExtras: false,
                enumExtras: [],
                stringExtraKeys: [],
                indexApplicable: () => false,
                number: 1,
                onUpdateCoord: vi.fn(),
                onUpdateExtra: vi.fn(),
                onRemove: vi.fn(),
                onCollapse: vi.fn(),
            },
        });

        expect(
            screen.queryByRole("button", { name: "Delete point" }),
        ).not.toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: "Done" }),
        ).toBeInTheDocument();
        expect(screen.queryByLabelText("B-scan")).not.toBeInTheDocument();
    });
});
