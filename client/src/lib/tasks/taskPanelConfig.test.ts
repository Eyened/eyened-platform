import { describe, it, expect } from "vitest";
import { parseTaskPanelConfig } from "./taskPanelConfig";

describe("parseTaskPanelConfig", () => {
    it("returns defaults when config is missing", () => {
        expect(parseTaskPanelConfig(undefined)).toEqual({
            enabled: true,
            expanded: false,
            sections: {
                title: true,
                nav: true,
                status: true,
                comments: true,
                overview: true,
            },
        });
    });

    it("returns defaults when task_panel is absent", () => {
        expect(
            parseTaskPanelConfig({ form_schema_name: "Naevi grading" }),
        ).toMatchObject({ enabled: true, expanded: false });
    });

    it("honors enabled false", () => {
        expect(
            parseTaskPanelConfig({ task_panel: { enabled: false } }).enabled,
        ).toBe(false);
    });

    it("merges partial sections onto defaults", () => {
        const result = parseTaskPanelConfig({
            task_panel: { expanded: true, sections: { comments: false } },
        });
        expect(result.expanded).toBe(true);
        expect(result.sections.comments).toBe(false);
        expect(result.sections.status).toBe(true);
        expect(result.sections.overview).toBe(true);
    });

    it("ignores unknown keys and wrong types", () => {
        const result = parseTaskPanelConfig({
            task_panel: {
                expanded: "yes",
                extra: 1,
                sections: { comments: "no", title: true },
            },
        });
        expect(result.expanded).toBe(false);
        expect(result.sections.comments).toBe(true);
        expect(result.sections.title).toBe(true);
        expect(result).not.toHaveProperty("extra");
    });

    it("treats a non-object task_panel as missing", () => {
        expect(parseTaskPanelConfig({ task_panel: [] }).enabled).toBe(true);
    });
});
