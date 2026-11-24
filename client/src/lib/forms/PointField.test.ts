import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import PointField from "./PointField.svelte";
import { pointArming } from "./pointArming.svelte";
import type { JSONSchema } from "./schemaType";
import { workspaceWith } from "$lib/workspace/testUtils";

vi.mock("svelte-sonner", () => ({
    toast: { warning: vi.fn(), success: vi.fn(), error: vi.fn() },
}));

const { toast } = await import("svelte-sonner");

const pointObject: JSONSchema = {
    type: "object",
    properties: {
        x: { type: "number" },
        y: { type: "number" },
        severity: {
            type: "string",
            enum: ["mild", "severe"] as unknown as never,
        },
        note: { type: "string" },
    },
    required: ["x", "y"],
};

const viewerContext = {
    image: {
        instance: { id: "img1" },
        is3D: false,
        image_id: "img1",
        width: 100,
    },
};

const volumeSchema = {
    "x-eyened-widget": "keypoint",
    title: "Volume",
    type: "object",
    properties: {
        x: { type: "number" },
        y: { type: "number" },
        index: { type: "integer" },
    },
    required: ["x", "y", "index"],
} as JSONSchema;

/** A workspace whose only viewport shows `instanceId` as a volume. */
function workspaceShowing(instanceId: string) {
    const ws = workspaceWith(1);
    const viewer = {
        image: { instance: { id: instanceId }, is3D: true, width: 100 },
        viewerSize: { width: 100 },
        setIndex: vi.fn(),
        focusPoint: vi.fn(),
    };
    ws.attachViewport(0, {
        zoomPercent: 100,
        zoomBy: vi.fn(),
        reset: vi.fn(),
        layers: { viewerContext: viewer } as never,
    });
    return { ws, viewer };
}

function renderField(
    props: Record<string, unknown>,
    context: Map<string, unknown> = new Map([["viewerContext", viewerContext]]),
) {
    return render(PointField, {
        props,
        context,
    } as never);
}

describe("PointField", () => {
    beforeEach(() => {
        pointArming.session = null;
        vi.mocked(toast.warning).mockClear();
    });

    it("warns when the schema is not a point widget", () => {
        renderField({
            schema: { type: "object", title: "Not points" },
            value: undefined,
            onchange: vi.fn(),
        });
        expect(
            screen.getByText("Point widget misconfigured for this schema."),
        ).toBeInTheDocument();
    });

    it("shows a hint when there is no viewer", () => {
        renderField(
            {
                schema: {
                    "x-eyened-widget": "keypoint",
                    title: "Fovea",
                    ...pointObject,
                },
                value: undefined,
                onchange: vi.fn(),
            },
            new Map(),
        );
        expect(
            screen.getByText("No viewer — tool unavailable"),
        ).toBeInTheDocument();
        expect(screen.getByText("Not placed")).toBeInTheDocument();
    });

    it("arms, edits, clears, and removes a single point", async () => {
        const onchange = vi.fn();
        renderField({
            schema: {
                "x-eyened-widget": "keypoint",
                title: "Fovea",
                description: "center",
                ...pointObject,
            },
            value: { x: 10, y: 20, severity: "mild", note: "n" },
            onchange,
        });

        expect(screen.getByText("Fovea")).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: "10, 20" }),
        ).toBeInTheDocument();

        await fireEvent.click(screen.getByRole("button", { name: "Move" }));
        expect(pointArming.isArmed("form:unknown:point")).toBe(true);
        expect(
            screen.getByRole("button", { name: "Stop placing" }),
        ).toBeInTheDocument();

        await fireEvent.click(screen.getByRole("button", { name: "10, 20" }));
        const x = screen.getByLabelText("x") as HTMLInputElement;
        await fireEvent.input(x, { target: { value: "11" } });
        expect(onchange).toHaveBeenCalled();

        await fireEvent.click(
            screen.getByRole("button", { name: "Delete point" }),
        );
        expect(onchange).toHaveBeenCalled();

        expect(onchange).toHaveBeenCalledWith(undefined);
    });

    it("Clear answer omits the field", async () => {
        const onchange = vi.fn();
        renderField({
            schema: {
                "x-eyened-widget": "keypoint",
                title: "Fovea",
                ...pointObject,
            },
            value: { x: 10, y: 20 },
            onchange,
        });
        await fireEvent.click(
            screen.getByRole("button", { name: "Clear answer: Fovea" }),
        );
        expect(onchange).toHaveBeenCalledWith(undefined);
    });

    it("renders a by-image list and updates extras", async () => {
        const onchange = vi.fn();
        renderField({
            schema: {
                "x-eyened-widget": "keypoint",
                title: "Lesions",
                type: "object",
                additionalProperties: {
                    type: "array",
                    items: pointObject,
                },
            },
            value: {
                img1: [{ x: 1, y: 2, severity: "mild" }],
                img2: [{ x: 3, y: 4 }],
            },
            onchange,
        });

        expect(screen.getByTitle("img1")).toBeInTheDocument();
        expect(screen.getByTitle("img2")).toBeInTheDocument();
        await fireEvent.click(
            screen.getByRole("button", { name: /^Point1 x1 y2/ }),
        );
        const trigger = screen.getByLabelText("severity");
        expect(trigger).toHaveTextContent("mild");
        trigger.focus();
        await fireEvent.keyDown(trigger, { key: "Enter" });
        const option = (await screen.findAllByRole("option")).find((o) =>
            o.textContent?.trim().startsWith("severe"),
        )!;
        await fireEvent.pointerDown(option, {
            button: 0,
            pointerType: "mouse",
        });
        await fireEvent.pointerUp(option, { button: 0, pointerType: "mouse" });
        expect(onchange).toHaveBeenCalled();
    });

    it("an empty B-scan on a volume field says so and saves nothing", async () => {
        const onchange = vi.fn();
        renderField({
            schema: volumeSchema,
            value: { x: 1, y: 2, index: 4 },
            onchange,
        });
        await fireEvent.click(
            screen.getByRole("button", { name: "1, 2 · B-scan 4" }),
        );
        const i = screen.getByLabelText("B-scan");
        await fireEvent.input(i, { target: { value: "" } });
        expect(screen.getByText("Enter a B-scan number.")).toBeInTheDocument();
        expect(i).toHaveAttribute("aria-invalid", "true");
        expect(onchange).not.toHaveBeenCalled();
        expect(toast.warning).not.toHaveBeenCalled();
    });

    it("a row click goes to its point in the viewport showing its image and opens the editor", async () => {
        const { ws, viewer } = workspaceShowing("img1");
        renderField(
            {
                schema: volumeSchema,
                value: { x: 30, y: 20, index: 4 },
                onchange: vi.fn(),
            },
            new Map<string, unknown>([
                ["viewerContext", viewerContext],
                ["workspace", ws],
            ]),
        );
        const chip = screen.getByRole("button", {
            name: "30, 20 · B-scan 4",
        });
        await fireEvent.click(chip);
        expect(viewer.setIndex).toHaveBeenCalledWith(4);
        expect(viewer.focusPoint).toHaveBeenCalledWith(30, 20, 1);
        expect(chip).toHaveAttribute("aria-expanded", "true");
        expect(screen.getByLabelText(/^B-scan/)).toBeInTheDocument();
    });

    it("with the point's image not open, only the editor opens, with a hint", async () => {
        const { ws, viewer } = workspaceShowing("other");
        renderField(
            {
                schema: volumeSchema,
                value: { x: 30, y: 20, index: 4 },
                onchange: vi.fn(),
            },
            new Map<string, unknown>([
                ["viewerContext", viewerContext],
                ["workspace", ws],
            ]),
        );
        await fireEvent.click(
            screen.getByRole("button", { name: "30, 20 · B-scan 4" }),
        );
        expect(viewer.focusPoint).not.toHaveBeenCalled();
        // Once in the editor, once in the live region.
        expect(
            screen.getAllByText("Open this image in the viewer first."),
        ).toHaveLength(2);
        expect(screen.getByRole("status")).toHaveTextContent(
            "Open this image in the viewer first.",
        );
        expect(screen.getByLabelText(/^B-scan/)).toBeInTheDocument();
    });

    it("draws a deleted slot of a sparse list as a muted numbered row", () => {
        const sparse = {
            "x-eyened-widget": "keypoint",
            title: "Landmarks",
            type: "array",
            items: {
                oneOf: [
                    {
                        type: "object",
                        properties: {
                            x: { type: "number" },
                            y: { type: "number" },
                        },
                        required: ["x", "y"],
                    },
                    { type: "null" },
                ],
            },
        } as JSONSchema;
        renderField({
            schema: sparse,
            value: [{ x: 1, y: 2 }, null, { x: 5, y: 6 }],
            onchange: vi.fn(),
        });
        expect(screen.getByText("2 · deleted")).toBeInTheDocument();
        expect(screen.getByText("2 points")).toBeInTheDocument();
    });

    it("writes null index for oct space when the field is blanked", async () => {
        const onchange = vi.fn();
        renderField({
            schema: {
                "x-eyened-widget": "keypoint",
                title: "OCT",
                type: "object",
                properties: {
                    x: { type: "number" },
                    y: { type: "number" },
                    index: { type: ["integer", "null"] },
                },
                required: ["x", "y"],
            },
            value: { x: 1, y: 2, index: 4 },
            onchange,
        });

        await fireEvent.click(
            screen.getByRole("button", { name: "1, 2 · B-scan 4" }),
        );
        const i = screen.getByLabelText("B-scan") as HTMLInputElement;
        await fireEvent.input(i, { target: { value: "" } });
        expect(onchange).toHaveBeenCalledWith(
            expect.objectContaining({ index: null }),
        );
    });
});
