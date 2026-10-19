import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/svelte";
import { formAnnotations } from "$lib/data/stores.svelte";
import type { FormSchemaGET } from "../../../types/openapi_types";

const openRegistrationEditor = vi.fn();
const openSeriesBlend = vi.fn();

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
            instanceIds: ["imgB", "imgA", "imgL"],
            openRegistrationEditor,
            openSeriesBlend,
        },
    ],
]);

describe("PanelRegistration", () => {
    beforeEach(() => {
        formAnnotations.clear();
        openRegistrationEditor.mockReset();
        openSeriesBlend.mockReset();
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

    function openButton(group: HTMLElement) {
        const button = [...group.querySelectorAll("button")].find(
            (item) => item.textContent?.trim() === "Open",
        );
        if (!button) throw new Error("Open button missing");
        return button;
    }

    async function pick(role: "Fixed" | "Moving", imageId: string) {
        await fireEvent.click(
            screen.getByRole("button", { name: `${role} ${imageId}` }),
        );
    }

    function renderPanel() {
        return render(PanelRegistration, {
            props: { active: true, registrationSchema: schema },
            context: contexts,
        } as never);
    }

    it("lists a group in top-row order with a thumbnail", () => {
        renderPanel();
        const right = screen.getByRole("group", { name: "Patient 100 R" });
        const fixedThumbs = [
            ...right.querySelectorAll(".role:first-of-type button.thumb"),
        ];
        expect(
            fixedThumbs.map((button) => button.getAttribute("aria-label")),
        ).toEqual(["Fixed imgB", "Fixed imgA"]);
        expect(fixedThumbs[0].querySelector("img")).toHaveAttribute(
            "src",
            "/api/images/imgB/thumbnail?size=144",
        );
        expect(fixedThumbs[0]).toHaveAttribute("title", "imgB");
        expect(
            screen.getByRole("button", { name: "Moving imgB" }),
        ).toBeInTheDocument();
    });

    it("groups a known eye apart from the other eye", () => {
        renderPanel();
        const right = screen.getByRole("group", { name: "Patient 100 R" });
        const leftGroup = screen.getByRole("group", { name: "Patient 100 L" });
        expect(right.querySelector('[aria-label="Fixed imgA"]')).toBeTruthy();
        expect(right.querySelector('[aria-label="Fixed imgB"]')).toBeTruthy();
        expect(
            leftGroup.querySelector('[aria-label="Fixed imgL"]'),
        ).toBeTruthy();
        expect(right.querySelector('[aria-label="Fixed imgL"]')).toBeNull();
    });

    it("opens an existing annotation without creating one", async () => {
        renderPanel();
        const right = screen.getByRole("group", { name: "Patient 100 R" });
        const open = openButton(right);
        expect(open).toBeDisabled();
        await pick("Fixed", "imgA");
        await pick("Moving", "imgB");
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
        await pick("Fixed", "imgA");
        await pick("Moving", "imgB");
        expect(createFormAnnotation).not.toHaveBeenCalled();
        await fireEvent.change(right.querySelector("select")!, {
            target: { value: "new" },
        });
        await fireEvent.click(openButton(right));
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

    it("ignores a second Open click while create is in flight", async () => {
        let resolveCreate!: (value: { id: number }) => void;
        const createPromise = new Promise<{ id: number }>((resolve) => {
            resolveCreate = resolve;
        });
        vi.mocked(createFormAnnotation).mockReturnValue(createPromise);

        renderPanel();
        const right = screen.getByRole("group", { name: "Patient 100 R" });
        await pick("Fixed", "imgA");
        await pick("Moving", "imgB");
        await fireEvent.change(right.querySelector("select")!, {
            target: { value: "new" },
        });
        const open = openButton(right);
        await fireEvent.click(open);
        expect(createFormAnnotation).toHaveBeenCalledTimes(1);

        await fireEvent.click(open);
        expect(createFormAnnotation).toHaveBeenCalledTimes(1);
        expect(openRegistrationEditor).not.toHaveBeenCalled();

        resolveCreate({ id: 22 });
        await waitFor(() => {
            expect(openRegistrationEditor).toHaveBeenCalledTimes(1);
        });
    });

    it("omits non-2D images and keeps 2D images as thumbnails", () => {
        const flat = { ...image("img2d", "R"), is2D: true };
        const volume = { ...image("imgVol", "R"), is2D: false };
        render(PanelRegistration, {
            props: { active: true, registrationSchema: schema },
            context: new Map([
                ...contexts,
                [
                    "viewerWindowContext",
                    {
                        topViewers: new Map([
                            [flat, {}],
                            [volume, {}],
                        ]),
                        openRegistrationEditor,
                    },
                ],
            ]),
        } as never);
        expect(
            screen.getByRole("button", { name: "Fixed img2d" }),
        ).toBeInTheDocument();
        expect(
            screen.queryByRole("button", { name: "Fixed imgVol" }),
        ).not.toBeInTheDocument();
    });

    it("hides annotations the current user cannot edit", () => {
        formAnnotations.set(22, {
            id: 22,
            form_schema_id: 4,
            patient_id: 100,
            laterality: "R",
            image_id: null,
            creator: { id: 9, name: "other" },
            form_data: {},
        } as never);
        render(PanelRegistration, {
            props: { active: true, registrationSchema: schema },
            context: new Map([
                ...contexts,
                [
                    "globalContext",
                    {
                        canEdit: (annotation: { creator: { id: number } }) =>
                            annotation.creator.id === 5,
                    },
                ],
            ]),
        } as never);
        const right = screen.getByRole("group", { name: "Patient 100 R" });
        expect(right).toHaveTextContent("me [21]");
        expect(right).not.toHaveTextContent("other [22]");
    });

    function viewBlendButton(group: HTMLElement) {
        const button = [...group.querySelectorAll("button")].find(
            (item) => item.textContent?.trim() === "View blend",
        );
        if (!button) throw new Error("View blend button missing");
        return button;
    }

    it("opens a series blend in top-row order", async () => {
        renderPanel();
        const right = screen.getByRole("group", { name: "Patient 100 R" });
        const view = viewBlendButton(right);
        expect(view).toBeDisabled();
        await fireEvent.click(
            screen.getByRole("button", { name: "Blend imgA" }),
        );
        expect(view).toBeDisabled();
        await fireEvent.click(
            screen.getByRole("button", { name: "Blend imgB" }),
        );
        expect(view).toBeEnabled();
        await fireEvent.click(view);
        expect(openSeriesBlend).toHaveBeenCalledWith({
            imageIds: ["imgB", "imgA"],
        });
    });

    it("does not open the editor when create fails", async () => {
        vi.mocked(createFormAnnotation).mockRejectedValue(new Error("nope"));
        renderPanel();
        const right = screen.getByRole("group", { name: "Patient 100 R" });
        await pick("Fixed", "imgA");
        await pick("Moving", "imgB");
        await fireEvent.change(right.querySelector("select")!, {
            target: { value: "new" },
        });
        await fireEvent.click(openButton(right));
        await waitFor(() => expect(createFormAnnotation).toHaveBeenCalled());
        expect(openRegistrationEditor).not.toHaveBeenCalled();
    });
});
