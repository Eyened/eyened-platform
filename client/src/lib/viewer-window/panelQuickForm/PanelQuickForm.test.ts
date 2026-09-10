import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/svelte";
import { formAnnotations, formSchemasByName } from "$lib/data/stores.svelte";
import type {
    FormAnnotationGET,
    FormSchemaGET,
} from "../../../types/openapi_types";

vi.mock("$lib/data", async (importOriginal) => {
    const actual = await importOriginal<typeof import("$lib/data")>();
    return {
        ...actual,
        createFormAnnotation: vi.fn(),
    };
});

vi.mock("../panelForm/openFormInNewWindow", () => ({
    openFormInNewWindow: vi.fn(),
}));

const { createFormAnnotation } = await import("$lib/data");
const { openFormInNewWindow } = await import(
    "../panelForm/openFormInNewWindow"
);
const { default: PanelQuickForm } = await import("./PanelQuickForm.svelte");

const schema: FormSchemaGET = {
    id: 10,
    name: "Naevi grading",
    entity_type: "ImageInstance",
    schema: { type: "object", properties: {} },
} as FormSchemaGET;

const contexts = new Map<string, unknown>([
    ["globalContext", { user: { id: 5 }, canEdit: () => true }],
    [
        "taskContext",
        {
            task: {
                task_definition: {
                    config: { form_schema_name: "Naevi grading" },
                },
            },
            subTask: { id: 7 },
        },
    ],
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
        },
    ],
]);

describe("PanelQuickForm", () => {
    beforeEach(() => {
        formSchemasByName.clear();
        formAnnotations.clear();
        vi.mocked(createFormAnnotation).mockReset();
        vi.mocked(openFormInNewWindow).mockReset();
    });

    it("warns when the schema is not configured", () => {
        render(PanelQuickForm, {
            props: {},
            context: new Map([
                ["globalContext", { user: { id: 5 }, canEdit: () => true }],
                [
                    "taskContext",
                    {
                        task: { task_definition: { config: {} } },
                        subTask: { id: 7 },
                    },
                ],
                [
                    "viewerContext",
                    {
                        image: {
                            instance: {
                                id: "img1",
                                patient: { id: 100 },
                            },
                        },
                    },
                ],
            ]),
        } as never);

        expect(
            screen.getByText("Form schema not configured or not found."),
        ).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Grade" })).toBeDisabled();
    });

    it("creates and opens a new annotation", async () => {
        formSchemasByName.set("Naevi grading", schema);
        const created = { id: 99, form_schema_id: 10 } as FormAnnotationGET;
        vi.mocked(createFormAnnotation).mockResolvedValue(created);

        render(PanelQuickForm, { props: {}, context: contexts } as never);

        expect(screen.getByText("Schema: Naevi grading")).toBeInTheDocument();
        expect(screen.getByText("Scope: ImageInstance")).toBeInTheDocument();
        expect(screen.getByText("Status: Not graded")).toBeInTheDocument();

        await fireEvent.click(screen.getByRole("button", { name: "Grade" }));
        expect(createFormAnnotation).toHaveBeenCalledWith(
            expect.objectContaining({
                form_schema_id: 10,
                image_id: "img1",
                sub_task_id: 7,
            }),
        );
        expect(openFormInNewWindow).toHaveBeenCalledWith(
            created,
            true,
            expect.anything(),
        );
    });

    it("does not create a second annotation when Grade is clicked twice in flight", async () => {
        formSchemasByName.set("Naevi grading", schema);
        let resolveCreate!: (value: FormAnnotationGET) => void;
        const pending = new Promise<FormAnnotationGET>((resolve) => {
            resolveCreate = resolve;
        });
        vi.mocked(createFormAnnotation).mockReturnValue(pending);

        render(PanelQuickForm, { props: {}, context: contexts } as never);

        const button = screen.getByRole("button", { name: "Grade" });
        await fireEvent.click(button);
        await fireEvent.click(button);

        expect(createFormAnnotation).toHaveBeenCalledTimes(1);

        const created = { id: 99, form_schema_id: 10 } as FormAnnotationGET;
        resolveCreate(created);

        await waitFor(() => {
            expect(openFormInNewWindow).toHaveBeenCalledTimes(1);
        });
        expect(openFormInNewWindow).toHaveBeenCalledWith(
            created,
            true,
            expect.anything(),
        );
    });

    it("opens an existing valid annotation", async () => {
        formSchemasByName.set("Naevi grading", schema);
        formAnnotations.set(3, {
            id: 3,
            form_schema_id: 10,
            creator: { id: 5, name: "me" },
            image_id: "img1",
            patient_id: 100,
            sub_task_id: 7,
            form_data: {},
        } as FormAnnotationGET);

        render(PanelQuickForm, { props: {}, context: contexts } as never);

        expect(screen.getByText("Status: Valid ✓")).toBeInTheDocument();
        await fireEvent.click(
            screen.getByRole("button", { name: "Open grading" }),
        );
        expect(createFormAnnotation).not.toHaveBeenCalled();
        expect(openFormInNewWindow).toHaveBeenCalled();
    });
});
