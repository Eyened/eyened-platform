import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import ETDRSGridItemLinked from "./ETDRSGridItemLinked.svelte";
import type { FormAnnotationGET } from "../../../types/openapi_types";

const formAnnotation = {
    id: 9,
    image_id: "img1",
    sub_task_id: 7,
    creator: { id: 1, name: "alice" },
} as FormAnnotationGET;

describe("ETDRSGridItemLinked", () => {
    it("toggles the overlay and marks the same subtask", async () => {
        const onToggleOverlay = vi.fn();
        render(ETDRSGridItemLinked, {
            props: {
                formAnnotation,
                overlayActive: false,
                onToggleOverlay,
            },
            context: new Map([["taskContext", { subTask: { id: 7 } }]]),
        } as never);

        expect(screen.getByText("alice")).toBeInTheDocument();
        expect(screen.getByText("[img1]")).toBeInTheDocument();
        expect(screen.getByText("[9]")).toBeInTheDocument();
        expect(document.querySelector("article")?.className).toContain(
            "same-sub-task",
        );

        await fireEvent.click(document.querySelector("span.icon")!);
        expect(onToggleOverlay).toHaveBeenCalledWith(formAnnotation);
    });

    it("does not mark a different subtask", () => {
        render(ETDRSGridItemLinked, {
            props: {
                formAnnotation,
                overlayActive: true,
                onToggleOverlay: vi.fn(),
            },
            context: new Map([["taskContext", { subTask: { id: 99 } }]]),
        } as never);

        expect(document.querySelector("article")?.className).not.toContain(
            "same-sub-task",
        );
    });
});
