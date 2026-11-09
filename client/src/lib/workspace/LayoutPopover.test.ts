import {
    fireEvent,
    render,
    screen,
    waitFor,
    within,
} from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import LayoutPopover from "./LayoutPopover.svelte";
import {
    expectNoAxeViolations,
    workspaceContext,
    workspaceWith,
} from "./testUtils";
import {
    readStripLocalizer,
    readStripOn,
    readStripTracking,
} from "./workspacePrefs";

async function open(ws = workspaceWith(20)) {
    const result = render(LayoutPopover, { context: workspaceContext(ws) });
    await fireEvent.click(screen.getByRole("button", { name: "Layout" }));
    await screen.findByRole("button", { name: "One viewport" });
    return { ws, ...result };
}

describe("LayoutPopover", () => {
    it("moves focus with the arrow keys without applying; a click applies", async () => {
        const { ws, container } = await open();
        const current = screen.getByRole("button", { name: "One viewport" });
        expect(current).toHaveAttribute("aria-pressed", "true");
        expect(current.tabIndex).toBe(0);
        await fireEvent.keyDown(current, { key: "ArrowDown" });
        const next = screen.getByRole("button", { name: "2 side by side" });
        await waitFor(() => expect(next).toHaveFocus());
        expect(next.tabIndex).toBe(0);
        expect(ws.preset.id).toBe("1x1");
        await fireEvent.click(next);
        expect(ws.preset.id).toBe("2x1");
        expect(screen.getByText("20 open: 2 pages")).toBeInTheDocument();
        await expectNoAxeViolations(container);
    });

    it("names the row that fits the open images for screen readers", async () => {
        await open(workspaceWith(11));
        expect(
            screen.getByRole("group", { name: "12 viewports" }),
        ).toHaveTextContent("Fits 11 open images");
    });

    it("closes when focus leaves it", async () => {
        await open();
        await fireEvent.focusOut(
            screen.getByRole("button", { name: "By visit" }),
            {
                relatedTarget: document.body,
            },
        );
        await waitFor(() =>
            expect(
                screen.queryByRole("button", { name: "One viewport" }),
            ).toBeNull(),
        );
    });

    it("opens from an outside anchor, starts on the current preset and returns focus to the anchor", async () => {
        const anchor = document.createElement("button");
        anchor.id = "menu-anchor";
        anchor.textContent = "Show menu";
        document.body.append(anchor);
        render(LayoutPopover, {
            props: { anchor: "#menu-anchor", open: true },
            context: workspaceContext(workspaceWith(20, { layout: "2x1" })),
        });
        expect(screen.queryByRole("button", { name: "Layout" })).toBeNull();
        const current = await screen.findByRole("button", {
            name: "2 side by side",
        });
        expect(current.tabIndex).toBe(0);
        await fireEvent.keyDown(current, { key: "Escape" });
        await waitFor(() => expect(anchor).toHaveFocus());
        anchor.remove();
    });
});

describe("LayoutPopover strip settings", () => {
    it("on /view turns the strip off and remembers it per browser; its settings hide with it", async () => {
        localStorage.clear();
        const ws = workspaceWith(3);
        render(LayoutPopover, {
            props: { stripToggle: true },
            context: workspaceContext(ws),
        });
        await fireEvent.click(screen.getByRole("button", { name: "Layout" }));
        const strip = await screen.findByRole("switch", {
            name: "Thumbnail strip",
        });
        expect(strip).toHaveAttribute("aria-checked", "true");
        expect(
            screen.getByRole("switch", { name: "Crosshair tracking" }),
        ).toBeInTheDocument();
        expect(
            screen.queryByRole("group", { name: "Localizer lines" }),
        ).toBeNull();
        await fireEvent.click(strip);
        expect(ws.strip).toBe(false);
        expect(readStripOn()).toBe(false);
        expect(
            screen.queryByRole("switch", { name: "Crosshair tracking" }),
        ).toBeNull();
    });

    it("in a task, shows the settings under a plain Thumbnail strip label and remembers them", async () => {
        localStorage.clear();
        const ws = workspaceWith(3);
        ws.hasLocalizers = true;
        const { container } = render(LayoutPopover, {
            context: workspaceContext(ws),
        });
        await fireEvent.click(screen.getByRole("button", { name: "Layout" }));
        const group = await screen.findByRole("group", {
            name: "Thumbnail strip",
        });
        expect(
            screen.queryByRole("switch", { name: "Thumbnail strip" }),
        ).toBeNull();
        await fireEvent.click(
            within(group).getByRole("switch", { name: "Crosshair tracking" }),
        );
        expect(ws.stripTracking).toBe(false);
        expect(readStripTracking()).toBe(false);
        await fireEvent.click(
            within(group).getByRole("radio", { name: "Current slice" }),
        );
        expect(ws.stripLocalizer).toBe("current");
        expect(readStripLocalizer()).toBe("current");
        await expectNoAxeViolations(container);
    });
});
