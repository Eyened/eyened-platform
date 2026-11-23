import { describe, expect, it, vi } from "vitest";

// Each PUT waits until the test settles it.
const puts = vi.hoisted(() => [] as ((value: unknown) => void)[]);
vi.mock("$lib/api/client", () => ({
    api: { PUT: vi.fn(() => new Promise((resolve) => puts.push(resolve))) },
    apiErrorFromResponse: vi.fn(),
    fetchApi: vi.fn(),
}));
vi.mock("$lib/data/api", () => ({
    apiInvoke: (call: () => Promise<unknown>) => call(),
    apiInvokeAllowEmpty: (call: () => Promise<unknown>) => call(),
}));
const tools = vi.hoisted(
    () =>
        [] as {
            points: unknown[];
            opts: {
                onChange: (points: unknown) => void;
                onPersist: (points: unknown) => void;
            };
        }[],
);
vi.mock("$lib/viewer/tools/PointTool.svelte", () => ({
    PointTool: vi.fn().mockImplementation(function (
        this: { points: unknown[]; opts: unknown; destroy: () => void },
        opts: unknown,
    ) {
        this.points = [];
        this.opts = opts;
        this.destroy = () => {};
        tools.push(this as never);
    }),
}));

const { formAnnotations } = await import("$lib/data/stores.svelte");
const { bindRegistrationPointTool } = await import(
    "./bindRegistrationPointTool"
);

describe("bindRegistrationPointTool, a save's reply", () => {
    it("doesn't reset a drag that started before it came back", async () => {
        formAnnotations.set(31, {
            id: 31,
            form_data: { img: [{ x: 1, y: 2 }] },
        } as never);
        const binding = bindRegistrationPointTool({
            viewerContext: {
                image: { image_id: "img", instance: { id: "img" } },
                addOverlay: () => () => {},
            } as never,
            annotationId: 31,
            // The same schema as bindRegistrationPointTool.test.ts.
            schema: {
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
            } as never,
            canEdit: true,
            pointMarker: { style: "cross", radius: 4, color: "red" },
        });
        const tool = tools.at(-1)!;
        tool.opts.onPersist([{ x: 3, y: 4 }]);
        // The grader starts the next drag while that save is out.
        tool.opts.onChange([{ x: 5, y: 6 }]);
        tool.points = [{ x: 5, y: 6 }];
        puts[0]({ data: {} });
        await new Promise((resolve) => setTimeout(resolve, 0));
        // MainViewer passes every store change to sync().
        binding.sync(formAnnotations.get(31)?.form_data);
        expect(tool.points).toEqual([{ x: 5, y: 6 }]);
    });
});
