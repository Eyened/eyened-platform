import {
    fireEvent,
    render,
    screen,
    waitFor,
    within,
} from "@testing-library/svelte";
import { SvelteMap } from "svelte/reactivity";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
    formAnnotations,
    formSchemas,
    formSchemasByName,
} from "$lib/data/stores.svelte";
import { entry, NO_URL } from "$lib/workspace/testUtils";
import { Workspace } from "$lib/workspace/workspace.svelte";
import type { FormAnnotationGET } from "../../types/openapi_types";
import FormsPanel from "./FormsPanel.svelte";

vi.mock("$lib/data", async (original) => ({
    ...(await original<typeof import("$lib/data")>()),
    createFormAnnotation: vi.fn(),
    deleteFormAnnotation: vi.fn(async (id: number) => {
        formAnnotations.delete(id);
    }),
}));
vi.mock("$lib/newWindow", () => ({
    openBlankWindow: vi.fn(() => null),
    mountInWindow: vi.fn(),
}));

const ME = 5;
const SET = 77;
const QUALITY = {
    id: 1,
    name: "Image quality grading",
    entity_type: "ImageInstance",
    schema: {
        type: "object",
        required: ["quality"],
        properties: { quality: { type: "string" } },
    },
};
const NOTES = { ...QUALITY, id: 2, name: "Lesion notes" };

function image(id: string, laterality: "L" | "R", patientId = 1) {
    return {
        image_id: id,
        instance: {
            id,
            patient: { id: patientId, identifier: `P-000${patientId}` },
            study: { id: 10, date: "2024-05-02" },
            laterality,
            modality: "OCT",
            etdrs_field: null,
            device: { manufacturer: "Heidelberg", model: "Spectralis" },
        },
    };
}

function form(id: number, over: Partial<FormAnnotationGET> = {}) {
    return {
        id,
        form_schema_id: 1,
        patient_id: 1,
        study_id: 10,
        image_id: "img-a",
        laterality: "R",
        sub_task_id: SET,
        form_data: { quality: "good" },
        creator: { id: ME, name: "Me" },
        date_inserted: `2026-05-0${id % 10}T10:00:00`,
        annotation_type: "grader_form",
        ...over,
    } as FormAnnotationGET;
}

function renderGrading(config: unknown = { form_schema_name: QUALITY.name }) {
    const ws = new Workspace();
    ws.hydrate([entry("img-a"), entry("img-b", { eyeRank: 1 })], NO_URL);
    const images = new SvelteMap([
        ["img-a", image("img-a", "R")],
        ["img-b", image("img-b", "L")],
    ]);
    return render(FormsPanel, {
        context: new Map<string, unknown>([
            ["workspace", ws],
            ["viewerWindowContext", { images }],
            [
                "taskContext",
                {
                    task: { id: 7, num_tasks: 10, task_definition: { config } },
                    subTask: { id: SET, comments: "" },
                    subTaskIndex: 0,
                },
            ],
            [
                "globalContext",
                {
                    user: { id: ME },
                    canEdit: (a: FormAnnotationGET) => a.creator.id === ME,
                },
            ],
        ]),
    });
}

function renderView() {
    const ws = new Workspace();
    ws.hydrate([entry("img-a"), entry("img-b", { eyeRank: 1 })], NO_URL);
    const images = new SvelteMap([
        ["img-a", image("img-a", "R", 1)],
        ["img-b", image("img-b", "L", 2)],
    ]);
    return render(FormsPanel, {
        context: new Map<string, unknown>([
            ["workspace", ws],
            ["viewerWindowContext", { images }],
            [
                "globalContext",
                {
                    user: { id: ME },
                    canEdit: (a: FormAnnotationGET) => a.creator.id === ME,
                },
            ],
        ]),
    });
}

beforeEach(() => {
    formSchemas.clear();
    formSchemasByName.clear();
    formAnnotations.clear();
    for (const s of [QUALITY, NOTES]) {
        formSchemas.set(s.id, s as never);
        formSchemasByName.set(s.name, s as never);
    }
});

describe("FormsPanel in a task (Grading)", () => {
    it("counts only complete forms, not every row with a form", () => {
        formAnnotations.set(9101, form(9101));
        formAnnotations.set(
            9102,
            form(9102, { image_id: "img-b", laterality: "L", form_data: {} }),
        );
        renderGrading();
        // "Graded" (any form) would read 2 of 2.
        expect(screen.getByText("1 of 2 complete")).toBeInTheDocument();
        expect(
            screen.getByRole("button", {
                name: "OS · OCT · 2024-05-02, not complete",
            }),
        ).toBeInTheDocument();
    });

    it("a task naming a form that doesn't exist says so instead of the rows", () => {
        renderGrading({ form_schema_name: "Retired form" });
        expect(
            screen.getByText(`This task's form "Retired form" wasn't found`),
        ).toBeInTheDocument();
        expect(screen.queryByText(/of 2 complete/)).toBeNull();
    });

    it("someone else's form can be copied, not deleted", () => {
        formAnnotations.set(
            9101,
            form(9101, {
                form_schema_id: 2,
                creator: {
                    id: 8,
                    name: "J. de Vries",
                } as FormAnnotationGET["creator"],
            }),
        );
        renderGrading();
        const row = screen
            .getByRole("button", { name: /^Lesion notes, / })
            .closest<HTMLElement>("[data-layer-row]")!;
        expect(
            within(row).getByRole("button", { name: "Copy" }),
        ).toBeInTheDocument();
        expect(
            within(row).queryByRole("button", { name: "Delete form" }),
        ).toBeNull();
    });

    it("after deleting the middle of three forms, focus is on the next row", async () => {
        formAnnotations.set(9103, form(9103, { form_schema_id: 2 }));
        formAnnotations.set(9102, form(9102, { form_schema_id: 2 }));
        formAnnotations.set(9101, form(9101, { form_schema_id: 2 }));
        renderGrading();
        const rows = screen.getAllByRole("button", { name: /^Lesion notes, / });
        const middle = rows[1].closest<HTMLElement>("[data-layer-row]")!;
        await fireEvent.click(
            within(middle).getByRole("button", { name: "Delete form" }),
        );
        await fireEvent.click(screen.getByRole("button", { name: "Delete" }));
        await waitFor(() => expect(document.activeElement).toBe(rows[2]), {
            timeout: 3000,
        });
    });

    it("after deleting a group's only form, the group goes and focus is on Other forms", async () => {
        formAnnotations.set(9101, form(9101, { form_schema_id: 2 }));
        renderGrading();
        await fireEvent.click(
            screen.getByRole("button", { name: "Delete form" }),
        );
        await fireEvent.click(screen.getByRole("button", { name: "Delete" }));
        await waitFor(
            () =>
                expect(document.activeElement).toBe(
                    screen.getByRole("button", { name: /^Other forms/ }),
                ),
            { timeout: 3000 },
        );
    });
});

describe("FormsPanel on /view", () => {
    it("with several patients and no forms, says there are none", () => {
        renderView();
        expect(
            screen.getByText("No forms for these images yet."),
        ).toBeInTheDocument();
    });
});
