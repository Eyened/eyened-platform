import {
    fireEvent,
    render,
    screen,
    waitFor,
    within,
} from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import { IMAGE_MIME } from "./dragTypes";
import ImagesPanel from "./ImagesPanel.svelte";
import {
    entry,
    expectNoAxeViolations,
    instance,
    NO_URL,
    workspaceContext,
} from "./testUtils";
import { Workspace } from "./workspace.svelte";

function renderPanel() {
    const ws = new Workspace({ writeUrl: () => {} });
    ws.hydrate(
        [
            entry("img01"),
            entry("img02", { date: "2024-01-09" }),
            entry("img03", { patient: "P-000502" }),
        ],
        { ...NO_URL, layout: "2x1" },
    );
    const props = {
        titleFor: (id: string) => ({ patient: "x", rest: `title ${id}` }),
        instanceFor: (id: string) =>
            instance(id, { etdrs_field: id === "img02" ? "F2" : "F1" }),
        onaddimages: vi.fn(),
        onloaded: vi.fn(),
    };
    const { container } = render(ImagesPanel, {
        props,
        context: workspaceContext(ws),
    });
    return { ws, props, container };
}

describe("ImagesPanel", () => {
    it("is a listbox with a group per patient and visit, named by its two headings", async () => {
        const { container } = renderPanel();
        const listbox = screen.getByRole("listbox", { name: "Images" });
        expect(within(listbox).getAllByRole("group")).toHaveLength(3);
        // The second visit's group borrows the first group's patient heading.
        const later = screen.getByRole("group", {
            name: "P-000417 2024-01-09",
        });
        expect(within(later).getAllByRole("option")).toHaveLength(1);
        expect(
            screen.getByRole("group", { name: "P-000502 2023-05-04" }),
        ).toBeInTheDocument();
        await expectNoAxeViolations(container);
    });

    it("an option's name says which viewport shows it, or that none does", () => {
        renderPanel();
        expect(
            screen.getByRole("option", { name: /OD · CF F2.*in viewport 2$/ }),
        ).toBeInTheDocument();
        expect(
            screen.getAllByRole("option", { name: /not in view$/i }),
        ).toHaveLength(1);
    });

    it("has one tab stop, on the selected viewport's image; arrows move across groups without loading, Enter loads", async () => {
        const { ws, props } = renderPanel();
        const options = screen.getAllByRole("option");
        expect(options.filter((o) => o.tabIndex === 0)).toEqual([options[0]]);
        expect(options[0]).toHaveAttribute("aria-selected", "true");

        options[0].focus();
        await fireEvent.keyDown(options[0], { key: "ArrowDown" });
        await waitFor(() => expect(options[1]).toHaveFocus());
        await fireEvent.keyDown(options[1], { key: "End" });
        await waitFor(() => expect(options[2]).toHaveFocus());
        expect(options.filter((o) => o.tabIndex === 0)).toEqual([options[2]]);
        expect(ws.slots[0].imageId).toBe("img01");

        await fireEvent.keyDown(options[2], { key: "Enter" });
        expect(ws.slots[0].imageId).toBe("img03");
        expect(props.onloaded).toHaveBeenCalled();
    });

    it("clicking an image loads it into the selected viewport", async () => {
        const { ws, props } = renderPanel();
        await fireEvent.click(
            screen.getByRole("option", { name: /not in view$/i }),
        );
        expect(ws.slots[0].imageId).toBe("img03");
        expect(props.onloaded).toHaveBeenCalled();
    });

    it("dragging an image carries its id", async () => {
        renderPanel();
        const setData = vi.fn();
        await fireEvent.dragStart(
            screen.getByRole("option", { name: /in viewport 2$/ }),
            { dataTransfer: { setData, effectAllowed: "" } },
        );
        expect(setData).toHaveBeenCalledWith(IMAGE_MIME, "img02");
    });
});
