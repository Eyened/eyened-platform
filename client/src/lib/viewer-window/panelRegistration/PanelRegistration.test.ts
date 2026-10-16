import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/svelte";
import { formAnnotations } from "$lib/data/stores.svelte";
import type { FormSchemaGET } from "../../../types/openapi_types";

const openRegistrationEditor = vi.fn();

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

const { createFormAnnotation } = await import("$lib/data");
const { default: PanelRegistration } = await import(
    "./PanelRegistration.svelte"
);

const schema = { id: 4, name: "Registration", schema: {} } as FormSchemaGET;

function image(imageId: string, laterality: "L" | "R" | null) {
    return {
        image_id: imageId,
        instance: {
            id: imageId,
            patient: { id: 100 },
            study: { id: 50 },
            laterality,
        },
    };
}

const rightA = image("imgA", "R");
const rightB = image("imgB", "R");
const left = image("imgL", "L");

const contexts = new Map<string, unknown>([
    ["viewerContext", { image: { instance: rightA.instance } }],
    [
        "taskContext",
        { task: { task_definition: { config: {} } }, subTask: { id: 7 } },
    ],
    ["globalContext", { canEdit: () => true }],
    [
        "viewerWindowContext",
        {
            topViewers: new Map([
                [rightA, {}],
                [left, {}],
                [rightB, {}],
            ]),
            openRegistrationEditor,
        },
    ],
]);

describe("PanelRegistration", () => {
    beforeEach(() => {
        formAnnotations.clear();
        openRegistrationEditor.mockReset();
        vi.mocked(createFormAnnotation).mockReset();
        formAnnotations.set(21, {
            id: 21,
            form_schema_id: 4,
            patient_id: 100,
            laterality: "R",
            image_id: null,
            creator: { id: 5, name: "me" },
            form_data: {},
        } as never);
    });

    function renderPanel() {
        return render(PanelRegistration, {
            props: { active: true, registrationSchema: schema },
            context: contexts,
        } as never);
    }

    it("groups a known eye apart from the other eye", () => {
        renderPanel();
        const right = screen.getByRole("group", { name: "Patient 100 R" });
        const leftGroup = screen.getByRole("group", { name: "Patient 100 L" });
        expect(right).toHaveTextContent("imgA");
        expect(right).toHaveTextContent("imgB");
        expect(leftGroup).toHaveTextContent("imgL");
        expect(right).not.toHaveTextContent("imgL");
    });

    it("opens an existing annotation without creating one", async () => {
        renderPanel();
        const right = screen.getByRole("group", { name: "Patient 100 R" });
        const open = right.querySelector("button")!;
        expect(open).toBeDisabled();
        await fireEvent.click(screen.getByRole("checkbox", { name: "imgA" }));
        await fireEvent.click(screen.getByRole("checkbox", { name: "imgB" }));
        expect(open).toBeDisabled();
        await fireEvent.change(right.querySelector("select")!, {
            target: { value: "21" },
        });
        expect(open).toBeEnabled();
        await fireEvent.click(open);
        expect(createFormAnnotation).not.toHaveBeenCalled();
        expect(openRegistrationEditor).toHaveBeenCalledWith({
            imageIds: ["imgA", "imgB"],
            annotationId: 21,
        });
    });

    it("creates a new annotation only when Open is clicked", async () => {
        vi.mocked(createFormAnnotation).mockResolvedValue({ id: 22 });
        renderPanel();
        const right = screen.getByRole("group", { name: "Patient 100 R" });
        await fireEvent.click(screen.getByRole("checkbox", { name: "imgB" }));
        await fireEvent.click(screen.getByRole("checkbox", { name: "imgA" }));
        expect(createFormAnnotation).not.toHaveBeenCalled();
        await fireEvent.change(right.querySelector("select")!, {
            target: { value: "new" },
        });
        await fireEvent.click(right.querySelector("button")!);
        await waitFor(() => {
            expect(createFormAnnotation).toHaveBeenCalledWith(
                expect.objectContaining({
                    form_schema_id: 4,
                    patient_id: 100,
                    laterality: "R",
                    image_id: "imgA",
                    study_id: 50,
                    sub_task_id: 7,
                    form_data: {},
                }),
            );
        });
        expect(openRegistrationEditor).toHaveBeenCalledWith({
            imageIds: ["imgA", "imgB"],
            annotationId: 22,
        });
    });

    it("does not open the editor when create fails", async () => {
        vi.mocked(createFormAnnotation).mockRejectedValue(new Error("nope"));
        renderPanel();
        const right = screen.getByRole("group", { name: "Patient 100 R" });
        await fireEvent.click(screen.getByRole("checkbox", { name: "imgA" }));
        await fireEvent.click(screen.getByRole("checkbox", { name: "imgB" }));
        await fireEvent.change(right.querySelector("select")!, {
            target: { value: "new" },
        });
        await fireEvent.click(right.querySelector("button")!);
        await waitFor(() => expect(createFormAnnotation).toHaveBeenCalled());
        expect(openRegistrationEditor).not.toHaveBeenCalled();
    });
});
