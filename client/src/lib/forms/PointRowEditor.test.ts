import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import PointRowEditor from "./PointRowEditor.svelte";

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
                coordLabel: "[10,21,3]",
                onUpdateCoord,
                onUpdateExtra,
                onRemove,
                onCollapse,
            },
        });

        expect(screen.getByText("[10,21,3]")).toBeInTheDocument();

        const x = screen.getByLabelText("x") as HTMLInputElement;
        await fireEvent.input(x, { target: { value: "15" } });
        expect(onUpdateCoord).toHaveBeenCalledWith("img1", 0, "x", "15");

        const y = screen.getByLabelText("y") as HTMLInputElement;
        await fireEvent.input(y, { target: { value: "25" } });
        expect(onUpdateCoord).toHaveBeenCalledWith("img1", 0, "y", "25");

        const i = screen.getByLabelText("i") as HTMLInputElement;
        await fireEvent.input(i, { target: { value: "" } });
        expect(onUpdateCoord).toHaveBeenCalledWith("img1", 0, "index", "");

        const select = screen.getByDisplayValue("mild") as HTMLSelectElement;
        await fireEvent.change(select, { target: { value: "severe" } });
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
            screen.getByRole("button", { name: "Remove point" }),
        );
        expect(onRemove).toHaveBeenCalled();

        await fireEvent.click(screen.getByRole("button", { name: "Done" }));
        expect(onCollapse).toHaveBeenCalled();
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
                coordLabel: "[1,2]",
                onUpdateCoord: vi.fn(),
                onUpdateExtra: vi.fn(),
                onRemove: vi.fn(),
                onCollapse: vi.fn(),
            },
        });

        expect(
            screen.queryByRole("button", { name: "Remove point" }),
        ).not.toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: "Done" }),
        ).toBeInTheDocument();
        expect(screen.queryByLabelText("i")).not.toBeInTheDocument();
    });
});
