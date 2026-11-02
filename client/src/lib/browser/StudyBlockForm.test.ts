import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { formAnnotations, formSchemas } from "$lib/data/stores.svelte";
import type {
    FormAnnotationGET,
    FormSchemaGET,
    StudyGET,
} from "../../types/openapi_types";

vi.mock("$lib/data", async (importOriginal) => {
    const actual = await importOriginal<typeof import("$lib/data")>();
    return {
        ...actual,
        deleteFormAnnotation: vi.fn(async (id: number) => {
            actual.formAnnotations.delete(id);
        }),
    };
});

const { deleteFormAnnotation } = await import("$lib/data");
const { default: StudyBlockForm } = await import("./StudyBlockForm.svelte");

const schema = { id: 1, name: "WARMGS" } as FormSchemaGET;
const study = { id: 42, patient: { id: 1 } } as unknown as StudyGET;
const form = (id: number) =>
    ({
        id,
        form_schema_id: 1,
        study_id: 42,
        laterality: null,
        creator: { id: 7, name: "Grader" },
        date_inserted: "2026-02-10T14:08:00",
    }) as unknown as FormAnnotationGET;

beforeEach(() => {
    formSchemas.clear();
    formSchemas.set(1, schema);
    formAnnotations.clear();
    formAnnotations.set(1, form(1));
    formAnnotations.set(2, form(2));
});

describe("StudyBlockForm", () => {
    it("deletes the chosen form once the danger modal is confirmed", async () => {
        render(StudyBlockForm, {
            props: {
                title: "WARMGS forms",
                formSchema: schema,
                split_laterality: false,
                study,
                create_new: false,
            },
            context: new Map([["globalContext", { canEdit: () => true }]]),
        });

        await fireEvent.click(
            screen.getAllByRole("button", { name: "Delete form" })[1],
        );
        await fireEvent.click(
            await screen.findByRole("button", { name: "Delete" }),
        );

        await waitFor(() =>
            expect(deleteFormAnnotation).toHaveBeenCalledWith(2),
        );
    });
});
