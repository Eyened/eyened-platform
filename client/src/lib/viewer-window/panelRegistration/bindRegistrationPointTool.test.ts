import { describe, expect, it, vi, beforeEach } from "vitest";
import { formAnnotations } from "$lib/data/stores.svelte";

const toolSpies = vi.hoisted(() => ({
    tools: [] as {
        points: { x: number; y: number }[];
        opts: { onPersist: (points: unknown) => void; canEdit: boolean };
        destroy: () => void;
    }[],
}));

vi.mock("$lib/viewer/tools/PointTool.svelte", () => ({
    PointTool: vi.fn().mockImplementation(function (
        this: {
            points: unknown[];
            opts: unknown;
            destroy: () => void;
        },
        opts: unknown,
    ) {
        this.points = [];
        this.opts = opts;
        this.destroy = () => {};
        toolSpies.tools.push(this as never);
    }),
}));

const { bindRegistrationPointTool } = await import(
    "./bindRegistrationPointTool"
);
const { setFormAnnotationValue } = await import("$lib/data");

vi.mock("$lib/data", async () => {
    const stores = await import("$lib/data/stores.svelte");
    return {
        formAnnotations: stores.formAnnotations,
        setFormAnnotationValue: vi.fn(),
    };
});

const schema = {
    type: "object",
    additionalProperties: {
        type: "array",
        items: {
            oneOf: [
                {
                    type: "object",
                    properties: {
                        x: { type: "number" },
                        y: { type: "number" },
                        index: { type: ["number", "null"] },
                    },
                    required: ["x", "y"],
                },
                { type: "null" },
            ],
        },
    },
};

describe("bindRegistrationPointTool", () => {
    beforeEach(() => {
        toolSpies.tools.length = 0;
        formAnnotations.clear();
        formAnnotations.set(21, {
            id: 21,
            form_data: { img: [{ x: 1, y: 2 }] },
        } as never);
        vi.mocked(setFormAnnotationValue).mockReset();
    });

    it("loads points and persists edits", () => {
        const addOverlay = vi.fn(() => vi.fn());
        const dispose = bindRegistrationPointTool({
            viewerContext: {
                image: { image_id: "img", instance: { id: "img" } },
                addOverlay,
            } as never,
            annotationId: 21,
            schema: schema as never,
            canEdit: true,
            pointMarker: { style: "cross", radius: 4, color: "red" },
        });
        expect(addOverlay).toHaveBeenCalledOnce();
        const tool = toolSpies.tools[0]!;
        expect(tool.points).toEqual([{ x: 1, y: 2 }]);
        tool.opts.onPersist([{ x: 3, y: 4 }]);
        expect(setFormAnnotationValue).toHaveBeenCalledWith(
            21,
            expect.objectContaining({ img: [{ x: 3, y: 4 }] }),
        );
        dispose();
    });

    it("keys projection images by instance id", () => {
        formAnnotations.set(21, {
            id: 21,
            form_data: { img: [{ x: 1, y: 2 }] },
        } as never);
        bindRegistrationPointTool({
            viewerContext: {
                image: { image_id: "img_proj", instance: { id: "img" } },
                addOverlay: () => () => {},
            } as never,
            annotationId: 21,
            schema: schema as never,
            canEdit: true,
            pointMarker: { style: "cross", radius: 4, color: "red" },
        });
        const tool = toolSpies.tools.at(-1)!;
        expect(tool.points).toEqual([{ x: 1, y: 2 }]);
        tool.opts.onPersist([{ x: 3, y: 4 }]);
        const written = vi
            .mocked(setFormAnnotationValue)
            .mock.calls.at(-1)?.[1];
        expect(written).toEqual({ img: [{ x: 3, y: 4 }] });
        expect(written).not.toHaveProperty("img_proj");
    });

    it("passes canEdit false through to the tool", () => {
        bindRegistrationPointTool({
            viewerContext: {
                image: { image_id: "img", instance: { id: "img" } },
                addOverlay: () => () => {},
            } as never,
            annotationId: 21,
            schema: schema as never,
            canEdit: false,
            pointMarker: { style: "cross", radius: 4, color: "red" },
        });
        expect(toolSpies.tools.at(-1)?.opts.canEdit).toBe(false);
    });
});
