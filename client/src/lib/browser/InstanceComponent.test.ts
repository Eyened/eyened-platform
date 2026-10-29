import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/svelte";
import type { ImageGET } from "../../types/openapi_types";

vi.mock("$lib/data/api", async (importOriginal) => ({
    ...(await importOriginal<typeof import("$lib/data/api")>()),
    fetchInstance: vi.fn(() => new Promise(() => {})),
}));

const { default: InstanceComponent } = await import(
    "./InstanceComponent.svelte"
);

const instance = {
    id: "1.2.3",
    modality: "ColorFundus",
    etdrs_field: "F2",
    tags: [],
} as unknown as ImageGET;

function renderTile() {
    const toggleInstance = vi.fn();
    render(InstanceComponent, {
        props: { instance },
        context: new Map([
            [
                "browserContext",
                { selectedIds: [], thumbnailSize: "8rem", toggleInstance },
            ],
        ]),
    });
    return toggleInstance;
}

describe("InstanceComponent", () => {
    it("toggles the selection with Enter on the tile", async () => {
        const toggleInstance = renderTile();
        await fireEvent.keyDown(
            screen.getByRole("checkbox", { name: "CFI F2 1.2.3" }),
            { key: "Enter" },
        );
        expect(toggleInstance).toHaveBeenCalledWith(instance);
    });

    it("opens image information without toggling the selection", async () => {
        const toggleInstance = renderTile();
        await fireEvent.click(
            screen.getByRole("button", { name: "Image information" }),
        );
        expect(await screen.findByRole("dialog")).toBeTruthy();
        expect(toggleInstance).not.toHaveBeenCalled();
    });
});
