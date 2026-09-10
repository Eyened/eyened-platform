import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/svelte";
import SchemaForm from "./SchemaForm.svelte";
import type { JSONSchema } from "./schemaType";

describe("SchemaForm", () => {
    it("renders a point widget field", () => {
        const schema: JSONSchema = {
            "x-eyened-widget": "keypoint",
            title: "Fovea",
            type: "object",
            properties: {
                x: { type: "number" },
                y: { type: "number" },
            },
            required: ["x", "y"],
        };
        render(SchemaForm, {
            props: {
                schema,
                value: { x: 1, y: 2 },
                onchange: vi.fn(),
            },
        });
        expect(screen.getByText("Fovea")).toBeInTheDocument();
        expect(screen.getByText("no point")).toBeInTheDocument();
    });

    it("passes fieldPath into nested object and array children", () => {
        const schema: JSONSchema = {
            type: "object",
            title: "Root",
            properties: {
                notes: {
                    type: "array",
                    title: "Notes",
                    items: { type: "string", title: "note" },
                },
            },
        };
        render(SchemaForm, {
            props: {
                schema,
                value: { notes: ["a"] },
                onchange: vi.fn(),
                collapse: false,
            },
        });
        expect(screen.getByText(/Root/)).toBeInTheDocument();
        expect(screen.getByText("Add note")).toBeInTheDocument();
    });
});
