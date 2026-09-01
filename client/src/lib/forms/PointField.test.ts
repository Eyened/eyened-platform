import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import PointField from "./PointField.svelte";
import { pointArming } from "./pointArming.svelte";
import type { JSONSchema } from "./schemaType";

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
        expect(screen.getByText("no point")).toBeInTheDocument();
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
        expect(screen.getByText("center")).toBeInTheDocument();
        expect(screen.getByText("[10,20]")).toBeInTheDocument();
        expect(screen.getByText("mild, n")).toBeInTheDocument();

        await fireEvent.click(
            screen.getByRole("button", { name: "Activate tool" }),
        );
        expect(pointArming.isArmed("form:unknown:point")).toBe(true);
        expect(
            screen.getByRole("button", { name: "Deactivate tool" }),
        ).toBeInTheDocument();

        await fireEvent.click(screen.getByText("[10,20]"));
        const x = screen.getByLabelText("x") as HTMLInputElement;
        await fireEvent.input(x, { target: { value: "11" } });
        expect(onchange).toHaveBeenCalled();

        await fireEvent.click(
            screen.getByRole("button", { name: "Remove point" }),
        );
        expect(onchange).toHaveBeenCalled();

        await fireEvent.click(screen.getByRole("button", { name: "Clear" }));
        await fireEvent.click(screen.getByRole("button", { name: "Remove" }));
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

        expect(screen.getByText("img1")).toBeInTheDocument();
        expect(screen.getByText("img2")).toBeInTheDocument();
        await fireEvent.click(screen.getByText("[1,2]"));
        const select = screen.getByDisplayValue("mild") as HTMLSelectElement;
        await fireEvent.change(select, { target: { value: "severe" } });
        expect(onchange).toHaveBeenCalled();
    });

    it("warns when blanking a required volume index", async () => {
        renderField({
            schema: {
                "x-eyened-widget": "keypoint",
                title: "Volume",
                type: "object",
                properties: {
                    x: { type: "number" },
                    y: { type: "number" },
                    index: { type: "integer" },
                },
                required: ["x", "y", "index"],
            },
            value: { x: 1, y: 2, index: 4 },
            onchange: vi.fn(),
        });

        await fireEvent.click(screen.getByText("[1,2,4]"));
        const i = screen.getByLabelText("i") as HTMLInputElement;
        await fireEvent.input(i, { target: { value: "" } });
        expect(toast.warning).toHaveBeenCalled();
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

        await fireEvent.click(screen.getByText("[1,2,4]"));
        const i = screen.getByLabelText("i") as HTMLInputElement;
        await fireEvent.input(i, { target: { value: "" } });
        expect(onchange).toHaveBeenCalledWith(
            expect.objectContaining({ index: null }),
        );
    });
});
