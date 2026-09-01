import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import type { FormAnnotationGET } from "../../../types/openapi_types";

vi.mock("$lib/data", () => ({
    deleteFormAnnotation: vi.fn(),
}));

const { deleteFormAnnotation } = await import("$lib/data");
const { default: ETDRSGridItem } = await import("./ETDRSGridItem.svelte");

const formAnnotation = {
    id: 11,
    image_id: "img1",
    sub_task_id: 7,
    creator: { id: 5, name: "alice" },
    form_data: { fovea: { x: 1.2, y: 3.8 }, disc_edge: { x: 9, y: 8 } },
} as FormAnnotationGET;

const context = new Map([
    ["globalContext", { canEdit: () => true }],
    ["taskContext", { subTask: { id: 7 } }],
]);

describe("ETDRSGridItem", () => {
    it("formats landmarks and forwards actions", async () => {
        const onToggleOverlay = vi.fn();
        const onSelect = vi.fn();
        const onRemove = vi.fn();
        const onArmLandmark = vi.fn();

        render(ETDRSGridItem, {
            props: {
                formAnnotation,
                overlayActive: false,
                selected: true,
                armedField: "fovea",
                onToggleOverlay,
                onSelect,
                onRemove,
                onArmLandmark,
            },
            context,
        } as never);

        expect(screen.getByText("alice")).toBeInTheDocument();
        expect(screen.getByText("[1, 4]")).toBeInTheDocument();
        expect(screen.getByText("[9, 8]")).toBeInTheDocument();

        await fireEvent.click(screen.getByText("alice"));
        expect(onSelect).toHaveBeenCalledWith(formAnnotation);

        await fireEvent.click(screen.getByRole("button", { name: /Fovea/ }));
        expect(onArmLandmark).toHaveBeenCalledWith(formAnnotation, "fovea");

        await fireEvent.click(screen.getByRole("button", { name: /Disc/ }));
        expect(onArmLandmark).toHaveBeenCalledWith(formAnnotation, "disc_edge");

        const icons = document.querySelectorAll("span.icon");
        await fireEvent.click(icons[0]!);
        expect(onToggleOverlay).toHaveBeenCalledWith(formAnnotation);

        await fireEvent.click(icons[1]!);
        expect(onRemove).toHaveBeenCalledWith(formAnnotation);
        expect(deleteFormAnnotation).toHaveBeenCalledWith(11);
    });

    it("disables landmark buttons when not editable", () => {
        render(ETDRSGridItem, {
            props: {
                formAnnotation: { ...formAnnotation, form_data: {} },
                overlayActive: true,
                selected: false,
                onToggleOverlay: vi.fn(),
                onSelect: vi.fn(),
                onRemove: vi.fn(),
                onArmLandmark: vi.fn(),
            },
            context: new Map([
                ["globalContext", { canEdit: () => false }],
                ["taskContext", { subTask: { id: 99 } }],
            ]),
        } as never);

        expect(screen.getAllByText("—")).toHaveLength(2);
        expect(screen.getByRole("button", { name: /Fovea/ })).toBeDisabled();
    });
});
