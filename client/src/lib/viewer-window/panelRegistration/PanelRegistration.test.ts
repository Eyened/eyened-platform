import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/svelte";
import { formAnnotations } from "$lib/data/stores.svelte";
import type {
    FormAnnotationGET,
    FormSchemaGET,
} from "../../../types/openapi_types";

vi.mock("$lib/data", async () => {
    const stores = await import("$lib/data/stores.svelte");
    return {
        formAnnotations: stores.formAnnotations,
        instances: stores.instances,
        createFormAnnotation: vi.fn(),
        deleteFormAnnotation: vi.fn(),
        setFormAnnotationValue: vi.fn(),
    };
});

const { createFormAnnotation, deleteFormAnnotation } = await import(
    "$lib/data"
);
const { default: PanelRegistration } = await import(
    "./PanelRegistration.svelte"
);

const schema = {
    id: 4,
    name: "Registration",
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
    },
} as FormSchemaGET;

const annotation = {
    id: 21,
    form_schema_id: 4,
    image_id: "img1",
    patient_id: 100,
    laterality: "R",
    creator: { id: 5, name: "me" },
    form_data: { img1: [{ x: 1, y: 2, index: null }] },
} as FormAnnotationGET;

const addOverlay = vi.fn(() => vi.fn());

const contexts = new Map<string, unknown>([
    [
        "viewerContext",
        {
            image: {
                instance: {
                    id: "img1",
                    patient: { id: 100 },
                    study: { id: 50 },
                    laterality: "R",
                },
            },
            addOverlay,
        },
    ],
    [
        "taskContext",
        {
            task: { task_definition: { config: {} } },
            subTask: { id: 7 },
        },
    ],
    ["globalContext", { canEdit: () => true }],
]);

describe("PanelRegistration", () => {
    beforeEach(() => {
        formAnnotations.clear();
        addOverlay.mockClear();
        vi.mocked(createFormAnnotation).mockReset();
        vi.mocked(deleteFormAnnotation).mockReset();
        formAnnotations.set(21, annotation);
    });

    it("lists annotations and arms a point tool", async () => {
        render(PanelRegistration, {
            props: { active: true, registrationSchema: schema },
            context: contexts,
        } as never);

        expect(screen.getByText("me")).toBeInTheDocument();
        await fireEvent.click(screen.getByText("me"));
        expect(addOverlay).toHaveBeenCalled();
        expect(screen.getByText(/\[1\]:/)).toBeInTheDocument();

        await fireEvent.click(screen.getByText("me"));
        expect(screen.queryByText(/\[1\]:/)).not.toBeInTheDocument();
    });

    it("creates a new annotation and activates it", async () => {
        const created = {
            ...annotation,
            id: 22,
            form_data: {},
        } as FormAnnotationGET;
        vi.mocked(createFormAnnotation).mockImplementation(async () => {
            formAnnotations.set(22, created);
            return created;
        });

        render(PanelRegistration, {
            props: { active: true, registrationSchema: schema },
            context: contexts,
        } as never);

        await fireEvent.click(
            screen.getByRole("button", { name: "Create new" }),
        );
        await waitFor(() => {
            expect(createFormAnnotation).toHaveBeenCalledWith(
                expect.objectContaining({
                    form_schema_id: 4,
                    image_id: "img1",
                    sub_task_id: 7,
                }),
            );
        });
        expect(addOverlay).toHaveBeenCalled();
    });

    it("removes an annotation", async () => {
        render(PanelRegistration, {
            props: { active: true, registrationSchema: schema },
            context: contexts,
        } as never);

        await fireEvent.click(document.querySelector("span.icon")!);
        expect(deleteFormAnnotation).toHaveBeenCalledWith(21);
    });
});
