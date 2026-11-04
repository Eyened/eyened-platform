import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import { IMAGE_MIME } from "./dragTypes";
import ImagesListShell from "./ImagesListShell.svelte";
import { entry, NO_URL, workspaceContext } from "./testUtils";
import { Workspace } from "./workspace.svelte";

function renderList() {
    const ws = new Workspace({ writeUrl: () => {} });
    ws.hydrate(
        [
            entry("img01"),
            entry("img02", { date: "2024-01-09" }),
            entry("img03", { patient: "P-000502" }),
        ],
        { ...NO_URL, layout: "2x1" },
        null,
    );
    const props = {
        titleFor: (id: string) => ({ patient: "x", rest: `title ${id}` }),
        onaddimages: vi.fn(),
        onloaded: vi.fn(),
    };
    render(ImagesListShell, { props, context: workspaceContext(ws) });
    return { ws, props };
}

describe("ImagesListShell", () => {
    it("groups by patient and visit date and marks images already in view", () => {
        renderList();
        expect(
            screen
                .getAllByRole("heading", { level: 3 })
                .map((h) => h.textContent?.trim()),
        ).toEqual(["P-000417", "P-000502"]);
        expect(
            screen
                .getAllByRole("heading", { level: 4 })
                .map((h) => h.textContent),
        ).toEqual(["2023-05-04", "2024-01-09", "2023-05-04"]);
        expect(screen.getAllByText("In view")).toHaveLength(2);
    });

    it("clicking an image loads it into the selected viewport", async () => {
        const { ws, props } = renderList();
        await fireEvent.click(
            screen.getByRole("button", { name: /title img03/ }),
        );
        expect(ws.slots[0].imageId).toBe("img03");
        expect(props.onloaded).toHaveBeenCalled();
    });

    it("dragging an image carries its id", async () => {
        renderList();
        const setData = vi.fn();
        await fireEvent.dragStart(
            screen.getByRole("button", { name: /title img02/ }),
            { dataTransfer: { setData, effectAllowed: "" } },
        );
        expect(setData).toHaveBeenCalledWith(IMAGE_MIME, "img02");
    });
});
