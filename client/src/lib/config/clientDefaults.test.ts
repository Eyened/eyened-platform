import { describe, it, expect } from "vitest";
import { CLIENT_DEFAULTS, mergeClientConfig } from "./clientDefaults";

describe("mergeClientConfig", () => {
    it("returns defaults when override is missing or not an object", () => {
        expect(mergeClientConfig(CLIENT_DEFAULTS, undefined)).toEqual(
            CLIENT_DEFAULTS,
        );
        expect(mergeClientConfig(CLIENT_DEFAULTS, null)).toEqual(
            CLIENT_DEFAULTS,
        );
    });

    it("overrides update_subtask_image_links", () => {
        const resolved = mergeClientConfig(CLIENT_DEFAULTS, {
            update_subtask_image_links: true,
        });
        expect(resolved.update_subtask_image_links).toBe(true);
        expect(resolved.layout).toEqual(CLIENT_DEFAULTS.layout);
    });

    it("replaces layout.hide and layout.prepend arrays (no concat)", () => {
        const resolved = mergeClientConfig(CLIENT_DEFAULTS, {
            layout: {
                hide: ["Form"],
                prepend: [
                    { type: "quick-form", title: "Grading", expanded: true },
                ],
            },
        });
        expect(resolved.layout.hide).toEqual(["Form"]);
        expect(resolved.layout.prepend).toEqual([
            { type: "quick-form", title: "Grading", expanded: true },
        ]);
    });

    it("ignores unknown keys", () => {
        const resolved = mergeClientConfig(CLIENT_DEFAULTS, {
            totally_unknown: 1,
            form_schema_name: "Naevi grading",
        });
        expect(resolved.form_schema_name).toBe("Naevi grading");
        expect(
            (resolved as Record<string, unknown>).totally_unknown,
        ).toBeUndefined();
    });
});
