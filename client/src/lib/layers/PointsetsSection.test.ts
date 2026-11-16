import {
    cleanup,
    fireEvent,
    render,
    screen,
    within,
} from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BUILTIN_VIEWER_FORM_SCHEMA_NAMES } from "$lib/config/builtinFormSchemas";
import { formAnnotations, formSchemasByName } from "$lib/data/stores.svelte";
import { expectNoAxeViolations } from "$lib/workspace/testUtils";
import type { FormAnnotationGET } from "../../types/openapi_types";
import { eyeKey } from "./pointsets";
import { fakeImage, layersContexts, ME } from "./testContexts";

vi.mock("$lib/data/api", async (original) => ({
    ...(await original<typeof import("$lib/data/api")>()),
    createFormAnnotation: vi.fn(),
    deleteFormAnnotation: vi.fn(async (id: number) => {
        formAnnotations.delete(id);
    }),
}));

const { createFormAnnotation, deleteFormAnnotation } = await import(
    "$lib/data/api"
);
const { default: PointsetsSection } = await import("./PointsetsSection.svelte");

const SCHEMA_NAME = BUILTIN_VIEWER_FORM_SCHEMA_NAMES.POINTSET_REGISTRATION;
const EYE = eyeKey({ patient: { id: 1 }, laterality: "R" });
const pt = { x: 1, y: 2 };

afterEach(() => {
    cleanup();
    formAnnotations.clear();
    formSchemasByName.delete(SCHEMA_NAME);
});

/** A synthetic registration of patient 1's right eye. */
function reg(
    id: number,
    creatorId: number,
    form_data: Record<string, unknown>,
    over: Partial<FormAnnotationGET> = {},
) {
    const a = {
        id,
        form_schema_id: 4,
        patient_id: 1,
        laterality: "R",
        image_id: "elsewhere",
        creator: { id: creatorId, name: `Grader ${creatorId}` },
        form_data,
        ...over,
    } as unknown as FormAnnotationGET;
    formAnnotations.set(id, a);
    return a;
}

function renderSection(
    instanceId = "inst-1",
    over: Parameters<typeof layersContexts>[1] = {},
) {
    formSchemasByName.set(SCHEMA_NAME, { id: 4, name: SCHEMA_NAME } as never);
    const ctx = layersContexts(instanceId, {
        images: [fakeImage("inst-2")],
        ...over,
    });
    const view = render(PointsetsSection, {
        props: { open: true, ontoggle: vi.fn() },
        context: ctx.context,
    });
    return { ...ctx, ...view };
}

describe("PointsetsSection", () => {
    it("lists this eye's registrations in id order, colleagues' too, with Delete only on your own, and passes axe", async () => {
        reg(12, 9, { "inst-1": [pt] });
        reg(11, ME, {}, { image_id: "inst-1" });
        reg(14, ME, { "inst-2": [pt] });
        const { container } = renderSection();
        const rows = screen.getAllByRole("group", { name: /^Registration/ });
        expect(rows.map((r) => r.getAttribute("aria-label"))).toEqual([
            "Registration [11]",
            "Registration [12]",
        ]);
        expect(within(rows[0]!).getByText("Mine")).toBeInTheDocument();
        expect(
            within(rows[0]!).getByRole("button", { name: "Delete" }),
        ).toBeInTheDocument();
        expect(within(rows[1]!).getByText("Grader 9")).toBeInTheDocument();
        expect(
            within(rows[1]!).queryByRole("button", { name: "Delete" }),
        ).toBeNull();
        await expectNoAxeViolations(container);
    });

    it("sets the eye's current registration for every viewport of that eye and shows its points and save state", async () => {
        reg(12, 9, { "inst-1": [pt, pt, pt], "inst-2": [pt, pt, null] });
        const first = renderSection();
        await fireEvent.click(
            screen.getByRole("button", { name: "Registration [12]" }),
        );
        expect(
            screen.getByRole("button", { name: "Registration [12]" }),
        ).toHaveAttribute("aria-pressed", "true");
        expect(screen.getByText("This CF 2022-05-10")).toBeInTheDocument();
        expect(screen.getByText("2 · no 3")).toBeInTheDocument();
        first.win.pointsets.sync.set(12, "error");
        expect(await screen.findByText("Couldn't save")).toBeInTheDocument();
        cleanup();
        // Another viewport of the same eye, showing the FAF.
        renderSection("inst-2", { images: [], win: first.win });
        expect(
            screen.getByRole("button", { name: "Registration [12]" }),
        ).toHaveAttribute("aria-pressed", "true");
    });

    it("New creates on this image, makes it current and arms P; a failed New says so and arms nothing", async () => {
        vi.mocked(createFormAnnotation).mockImplementationOnce(async (body) => {
            return reg(
                20,
                ME,
                {},
                { image_id: (body as { image_id: string }).image_id },
            );
        });
        const { win, workspace } = renderSection();
        // With no rows, the header's New and the empty state's button share the name; the header comes first.
        const newButton = () =>
            screen.getAllByRole("button", { name: "New registration" })[0]!;
        await fireEvent.click(newButton());
        expect(createFormAnnotation).toHaveBeenLastCalledWith(
            expect.objectContaining({
                form_schema_id: 4,
                image_id: "inst-1",
                patient_id: 1,
            }),
        );
        expect(win.pointsets.currentId(EYE)).toBe(20);
        expect(workspace.arm).toHaveBeenCalledWith("point");

        vi.mocked(createFormAnnotation).mockRejectedValueOnce(
            new Error("offline"),
        );
        workspace.arm.mockClear();
        await fireEvent.click(newButton());
        expect(
            await screen.findByText("Couldn't create a registration"),
        ).toBeInTheDocument();
        expect(workspace.arm).not.toHaveBeenCalled();
    });

    it("Delete asks first, then removes the registration", async () => {
        vi.mocked(deleteFormAnnotation).mockClear();
        reg(11, ME, {}, { image_id: "inst-1" });
        renderSection();
        await fireEvent.click(screen.getByRole("button", { name: "Delete" }));
        const dialog = await screen.findByRole("dialog", {
            name: /Delete registration/,
        });
        expect(deleteFormAnnotation).not.toHaveBeenCalled();
        await fireEvent.click(
            within(dialog).getByRole("button", { name: "Delete" }),
        );
        await vi.waitFor(() =>
            expect(deleteFormAnnotation).toHaveBeenCalledWith(11),
        );
    });

    it("offers no New when the eye has no other loaded 2D image", () => {
        renderSection("inst-1", {
            images: [fakeImage("inst-9", { laterality: "L" })],
        });
        expect(
            screen.queryByRole("button", { name: /New registration/ }),
        ).toBeNull();
    });
});
