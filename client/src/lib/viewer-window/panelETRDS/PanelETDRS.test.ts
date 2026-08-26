import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/svelte";
import { formAnnotations } from "$lib/data/stores.svelte";
import type {
    FormAnnotationGET,
    FormSchemaGET,
} from "../../../types/openapi_types";

vi.mock("cornerstone-wado-image-loader", () => ({ default: {} }));
vi.mock("@cornerstonejs/dicom-image-loader", () => ({ default: {} }));
vi.mock("cornerstone-core", () => ({ default: {} }));
vi.mock("../viewerWindowContext.svelte", () => ({
    ViewerWindowContext: class ViewerWindowContext {},
}));
vi.mock("$lib/viewer/overlays/ETDRSGridItemOverlay.svelte", () => ({
    ETDRSGridItemOverlay: class ETDRSGridItemOverlay {
        constructor() {}
        destroy() {}
    },
}));
vi.mock("$lib/data", async () => {
    const stores = await import("$lib/data/stores.svelte");
    return {
        formAnnotations: stores.formAnnotations,
        createFormAnnotation: vi.fn(),
        setFormAnnotationValue: vi.fn(),
    };
});

const { createFormAnnotation } = await import("$lib/data");
const { default: PanelETDRS } = await import("./PanelETDRS.svelte");

const schema = { id: 3, name: "ETDRS" } as FormSchemaGET;

const own = {
    id: 11,
    form_schema_id: 3,
    image_id: "img1",
    patient_id: 100,
    creator: { id: 5, name: "me" },
    form_data: { fovea: { x: 1, y: 2 }, disc_edge: { x: 3, y: 4 } },
    sub_task_id: 7,
} as FormAnnotationGET;

const linked = {
    id: 12,
    form_schema_id: 3,
    image_id: "other",
    patient_id: 100,
    creator: { id: 9, name: "other" },
    form_data: {},
    sub_task_id: 8,
} as FormAnnotationGET;

const addOverlay = vi.fn(() => vi.fn());

const contexts = new Map<string, unknown>([
    [
        "viewerWindowContext",
        {
            registration: {
                getLinkedImgIds: () => new Set(["other"]),
            },
        },
    ],
    [
        "viewerContext",
        {
            image: {
                image_id: "img1",
                instance: {
                    id: "img1",
                    patient: { id: 100 },
                    study: { id: 50 },
                    laterality: "R",
                    cf_keypoints: {
                        fovea_xy: [10, 11],
                        disc_edge_xy: [20, 21],
                    },
                },
            },
            addOverlay,
        },
    ],
    ["taskContext", { subTask: { id: 7 } }],
    ["globalContext", { user: { id: 5 }, canEdit: () => true }],
]);

describe("PanelETDRS", () => {
    beforeEach(() => {
        formAnnotations.clear();
        addOverlay.mockClear();
        vi.mocked(createFormAnnotation).mockReset();
        formAnnotations.set(11, own);
        formAnnotations.set(12, linked);
    });

    it("lists own and linked annotations and creates a new one", async () => {
        const created = {
            ...own,
            id: 99,
            form_data: {},
        } as FormAnnotationGET;
        vi.mocked(createFormAnnotation).mockImplementation(async () => {
            formAnnotations.set(99, created);
            return created;
        });

        render(PanelETDRS, {
            props: { active: true, etdrsSchema: schema },
            context: contexts,
        } as never);

        expect(screen.getByText("Automatic")).toBeInTheDocument();
        expect(screen.getByText("me")).toBeInTheDocument();
        expect(screen.getByText("other")).toBeInTheDocument();

        await fireEvent.click(
            screen.getByRole("button", { name: "Create new" }),
        );
        await waitFor(() => {
            expect(createFormAnnotation).toHaveBeenCalledWith(
                expect.objectContaining({
                    form_schema_id: 3,
                    image_id: "img1",
                    sub_task_id: 7,
                }),
            );
        });
        expect(addOverlay).toHaveBeenCalled();
    });

    it("selects, arms landmarks, and toggles overlays", async () => {
        render(PanelETDRS, {
            props: { active: true, etdrsSchema: schema },
            context: contexts,
        } as never);

        await fireEvent.click(screen.getByText("me"));
        expect(addOverlay).toHaveBeenCalled();

        await fireEvent.click(screen.getByRole("button", { name: /Disc/ }));
        await fireEvent.click(screen.getByRole("button", { name: /Fovea/ }));

        const icons = document.querySelectorAll("span.icon");
        await fireEvent.click(icons[0]!); // automatic show/hide
        await fireEvent.click(icons[1]!); // own overlay toggle
    });
});
