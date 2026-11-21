import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { BUILTIN_VIEWER_FORM_SCHEMA_NAMES } from "$lib/config/builtinFormSchemas";
import { formAnnotations, formSchemasByName } from "$lib/data/stores.svelte";
import { eyeKey } from "./pointsets";
import RegistrationSection from "./RegistrationSection.svelte";
import { layersContexts, ME } from "./testContexts";

const SCHEMA_NAME = BUILTIN_VIEWER_FORM_SCHEMA_NAMES.POINTSET_REGISTRATION;
const EYE = eyeKey({ patient: { id: 1 }, laterality: "R" });

afterEach(() => {
    cleanup();
    formAnnotations.clear();
    formSchemasByName.delete(SCHEMA_NAME);
});

describe("RegistrationSection", () => {
    it("picks the registration every viewport of this eye uses", async () => {
        formSchemasByName.set(SCHEMA_NAME, {
            id: 4,
            name: SCHEMA_NAME,
        } as never);
        for (const id of [20, 21])
            formAnnotations.set(id, {
                id,
                form_schema_id: 4,
                patient_id: 1,
                laterality: "R",
                image_id: "inst-1",
                creator: { id: ME, name: `Grader ${ME}` },
                form_data: {},
            } as never);
        const ctx = layersContexts("inst-1");
        render(RegistrationSection, {
            props: { open: true, ontoggle: vi.fn() },
            context: ctx.context,
        });
        const trigger = screen.getByRole("button", {
            name: "Registration · OD",
            expanded: false,
        });
        trigger.focus();
        await fireEvent.keyDown(trigger, { key: "Enter" });
        const option = (await screen.findAllByRole("option")).find((o) =>
            o.textContent?.startsWith("Registration [20]"),
        )!;
        await fireEvent.pointerDown(option, {
            button: 0,
            pointerType: "mouse",
        });
        await fireEvent.pointerUp(option, { button: 0, pointerType: "mouse" });
        expect(ctx.win.pointsets.currentId(EYE)).toBe(20);
    });
});
