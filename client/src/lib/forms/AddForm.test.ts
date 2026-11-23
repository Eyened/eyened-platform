import { fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { formSchemas } from "$lib/data/stores.svelte";
import type { ImageMeta } from "$lib/workspace/imageMeta";
import {
    readLastFormSchema,
    writeLastFormSchema,
} from "$lib/workspace/workspacePrefs";
import AddForm from "./AddForm.svelte";

const image = {
    imageId: "oct-1",
    instance: {
        id: "oct-1",
        patient: { id: 1, identifier: "P-0001" },
        study: { id: 10, date: "2024-05-02" },
        laterality: "R",
        modality: "OCT",
        etdrs_field: null,
        device: { manufacturer: "Heidelberg", model: "Spectralis" },
    } as unknown as ImageMeta,
};

beforeEach(() => {
    formSchemas.clear();
    formSchemas.set(1, {
        id: 1,
        name: "Image quality grading",
        entity_type: "ImageInstance",
    } as never);
    formSchemas.set(2, {
        id: 2,
        name: "DR severity",
        entity_type: "StudyEye",
    } as never);
    formSchemas.set(3, {
        id: 3,
        name: "Pointset registration",
        entity_type: "ImageInstance",
    } as never);
    localStorage.clear();
});
afterEach(() => vi.restoreAllMocks());

// The trigger's accessible name is "Form <chosen>" in a browser; jsdom leaves the chosen text out, so read it from the content.
function expectFormChosen(text: string) {
    expect(screen.getByRole("button", { name: /^Form/ })).toHaveTextContent(
        text,
    );
}

describe("AddForm", () => {
    it("starts on the task form in a task, whatever was used last", () => {
        writeLastFormSchema(1);
        render(AddForm, {
            props: { selectedImage: image, taskSchemaId: 2, onadd: vi.fn() },
        });
        expectFormChosen("DR severity");
    });

    it("on /view starts on the last form used", () => {
        writeLastFormSchema(1);
        render(AddForm, { props: { selectedImage: image, onadd: vi.fn() } });
        expectFormChosen("Image quality grading");
    });

    it("never starts on a registration schema, even when it was used last", () => {
        writeLastFormSchema(3);
        render(AddForm, { props: { selectedImage: image, onadd: vi.fn() } });
        expectFormChosen("DR severity");
    });

    it("with storage failing, starts on the first form", () => {
        vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
            throw new Error("blocked");
        });
        render(AddForm, { props: { selectedImage: image, onadd: vi.fn() } });
        expectFormChosen("DR severity");
    });

    it("adds for the selected image's target and remembers the form", async () => {
        const onadd = vi.fn();
        render(AddForm, {
            props: { selectedImage: image, taskSchemaId: 1, onadd },
        });
        expect(
            screen.getByText("For OD · OCT · 2024-05-02 (selected)"),
        ).toBeInTheDocument();
        await fireEvent.click(screen.getByRole("button", { name: "Add form" }));
        expect(onadd).toHaveBeenCalledWith(
            expect.objectContaining({ id: 1 }),
            expect.objectContaining({ name: "OD · OCT · 2024-05-02" }),
        );
        expect(readLastFormSchema()).toBe(1);
    });
});
