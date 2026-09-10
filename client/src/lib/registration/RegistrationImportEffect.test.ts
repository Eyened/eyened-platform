import { describe, it, expect, vi } from "vitest";
import { render } from "@testing-library/svelte";
import { tick } from "svelte";
import { Registration } from "./registration.svelte";
import RegistrationImportEffect from "./RegistrationImportEffect.svelte";

describe("Registration import from $effect", () => {
    it("does not infinite-loop when bumping revision inside the effect", async () => {
        const registration = new Registration();
        const onRun = vi.fn();

        render(RegistrationImportEffect, {
            props: { registration, trigger: 1, onRun },
        });
        await tick();
        await Promise.resolve(); // scheduled path recompute microtask

        expect(onRun.mock.calls.length).toBe(1);
        expect(registration.revision).toBeGreaterThan(0);
    });
});
