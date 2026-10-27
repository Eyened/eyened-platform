import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/svelte";
import Selection from "./Selection.svelte";

describe("Selection", () => {
    it("offers only View selected in overlay mode", () => {
        render(Selection, {
            props: {
                mode: "overlay",
                panelOpen: false,
                onviewselected: vi.fn(),
            },
            context: new Map([
                [
                    "browserContext",
                    {
                        selectedIds: ["a"],
                        selectedInstances: [],
                        openTab: vi.fn(),
                    },
                ],
            ]),
        });

        expect(
            screen.getByRole("button", { name: "View selected" }),
        ).toBeTruthy();
        for (const name of ["Cancel", "Open in viewer", "Tag"]) {
            expect(screen.queryByRole("button", { name })).toBeNull();
        }
    });
});
