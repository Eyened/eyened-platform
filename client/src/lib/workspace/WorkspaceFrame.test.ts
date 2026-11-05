import {
    cleanup,
    fireEvent,
    render,
    screen,
    waitFor,
} from "@testing-library/svelte";
import { createRawSnippet } from "svelte";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import {
    expectNoAxeViolations,
    mockWidth,
    workspaceContext,
    workspaceWith,
} from "./testUtils";
import type { Workspace } from "./workspace.svelte";
import WorkspaceFrame from "./WorkspaceFrame.svelte";
import type { TaskHeader } from "./WorkspaceHeader.svelte";

const viewer = createRawSnippet((imageId: () => string) => ({
    render: () => `<div data-testid="viewer-${imageId()}"></div>`,
}));
const tile = createRawSnippet((imageId: () => string) => ({
    render: () => `<div data-testid="tile-${imageId()}"></div>`,
}));
const titleFor = (imageId: string) => ({
    patient: "P-000417",
    rest: `OD · CF F1 · ${imageId}`,
});

function taskHeader(): TaskHeader {
    return {
        label: "Set 1234 of 5000",
        prevDisabled: false,
        nextDisabled: false,
        prev: vi.fn(),
        next: vi.fn(),
        overview: vi.fn(),
    };
}

function renderFrame(ws: Workspace, task: TaskHeader | null = null) {
    return render(WorkspaceFrame, {
        props: {
            viewer,
            tile,
            titleFor,
            onaddimages: vi.fn(),
            emptyMessage: null,
            task,
        },
        context: workspaceContext(ws),
    });
}

/** The regions an open overlay must make inert. */
function underOverlay(container: HTMLElement): Element[] {
    return [
        container.querySelector(".tool-options")!,
        screen.getByRole("main"),
        container.querySelector(".pager")!,
    ];
}

// jsdom has no `inert` property, and Svelte sets it as a property; reflect it so the attribute is observable.
beforeAll(() => {
    if ("inert" in HTMLElement.prototype) return;
    Object.defineProperty(HTMLElement.prototype, "inert", {
        configurable: true,
        get() {
            return this.hasAttribute("inert");
        },
        set(on: boolean) {
            this.toggleAttribute("inert", on);
        },
    });
});

beforeEach(() => {
    localStorage.clear();
});

describe("WorkspaceFrame", () => {
    it("opens Images by default with the strip off and folds the right column below xlg", async () => {
        mockWidth({ md: true, xlg: false });
        const ws = workspaceWith(3);
        ws.strip = false;
        const { container } = renderFrame(ws);
        expect(
            screen.getByRole("region", { name: "Images" }),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: "Show Layers" }),
        ).toBeInTheDocument();
        await expectNoAxeViolations(container);
    });

    it("with the strip on, shows the strip and starts with Images closed", async () => {
        mockWidth({ md: true, xlg: true });
        const { container } = renderFrame(workspaceWith(3));
        expect(
            screen.getByRole("list", { name: "Thumbnails" }),
        ).toBeInTheDocument();
        expect(screen.queryByRole("region", { name: "Images" })).toBeNull();
        await expectNoAxeViolations(container);
    });

    it("remembers the open panel and the right column per user", async () => {
        mockWidth({ md: true, xlg: false });
        renderFrame(workspaceWith(3));
        await fireEvent.click(screen.getByRole("button", { name: "Info" }));
        await fireEvent.click(
            screen.getByRole("button", { name: "Show Layers" }),
        );
        expect(
            screen.getByRole("button", { name: "Hide Layers" }),
        ).toBeInTheDocument();
        cleanup();
        renderFrame(workspaceWith(3));
        expect(
            screen.getByRole("region", { name: "Info" }),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: "Hide Layers" }),
        ).toBeInTheDocument();
    });

    it("below md starts with the right column closed even when stored open, and has no icon columns", () => {
        localStorage.setItem("eyened:viewer:rightOpen", "true");
        mockWidth({ md: false, xlg: true });
        renderFrame(workspaceWith(3));
        expect(
            screen.queryByRole("navigation", { name: "Tools and panels" }),
        ).toBeNull();
        expect(
            screen.queryByRole("button", { name: "Show Layers" }),
        ).toBeNull();
        expect(screen.queryByRole("region", { name: "Layers" })).toBeNull();
        expect(screen.getByRole("main")).not.toHaveAttribute("inert");
    });

    it("below md the header button opens Layers and Grading over inert regions; Esc returns focus; nothing is stored", async () => {
        mockWidth({ md: false, xlg: false });
        const { container } = renderFrame(workspaceWith(3), taskHeader());
        const button = screen.getByRole("button", {
            name: "Show Layers and Grading",
        });
        await fireEvent.click(button);
        expect(
            screen.getByRole("region", { name: "Layers" }),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("region", { name: "Grading" }),
        ).toBeInTheDocument();
        await waitFor(() =>
            expect(
                screen.getByRole("heading", { name: "Layers" }),
            ).toHaveFocus(),
        );
        for (const el of underOverlay(container))
            expect(el).toHaveAttribute("inert");
        expect(button).toHaveAccessibleName("Hide Layers and Grading");
        await fireEvent.keyDown(
            screen.getByRole("heading", { name: "Layers" }),
            { key: "Escape" },
        );
        await waitFor(() => expect(button).toHaveFocus());
        for (const el of underOverlay(container))
            expect(el).not.toHaveAttribute("inert");
        expect(localStorage.getItem("eyened:viewer:rightOpen")).toBeNull();
        expect(
            document.body.style.getPropertyValue("--viewer-toast-right"),
        ).toBe("16px");
    });

    it("below md the menu holds Task overview, Layout…, the tools and Images; Esc closes it; nothing is stored", async () => {
        mockWidth({ md: false, xlg: false });
        const task = taskHeader();
        const { container } = renderFrame(workspaceWith(3), task);
        const menu = screen.getByRole("button", { name: "Show menu" });
        await fireEvent.click(menu);
        await waitFor(() =>
            expect(
                screen.getByRole("button", { name: "Task overview" }),
            ).toHaveFocus(),
        );
        expect(menu).toHaveAccessibleName("Hide menu");
        expect(
            screen.getByRole("button", { name: "Layout…" }),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("group", { name: "Tools" }),
        ).toBeInTheDocument();
        expect(screen.getByRole("tab", { name: "Images" })).toHaveAttribute(
            "aria-selected",
            "true",
        );
        expect(
            screen.getByRole("region", { name: "Images" }),
        ).toBeInTheDocument();
        await fireEvent.click(screen.getByRole("tab", { name: "Info" }));
        expect(
            screen.getByRole("region", { name: "Info" }),
        ).toBeInTheDocument();
        for (const el of underOverlay(container))
            expect(el).toHaveAttribute("inert");
        await expectNoAxeViolations(container);
        await fireEvent.keyDown(screen.getByRole("tab", { name: "Info" }), {
            key: "Escape",
        });
        await waitFor(() => expect(menu).toHaveFocus());
        expect(screen.queryByRole("region", { name: "Info" })).toBeNull();
        expect(localStorage.getItem("eyened:viewer:leftPanel")).toBeNull();
        await fireEvent.click(menu);
        await fireEvent.click(
            await screen.findByRole("button", { name: "Task overview" }),
        );
        expect(task.overview).toHaveBeenCalledTimes(1);
        expect(screen.queryByRole("region", { name: "Images" })).toBeNull();
    });

    it("below md Layout… closes the menu and opens the Layout popover; Esc returns focus to the menu button", async () => {
        mockWidth({ md: false, xlg: false });
        renderFrame(workspaceWith(3));
        const menu = screen.getByRole("button", { name: "Show menu" });
        await fireEvent.click(menu);
        await fireEvent.click(
            await screen.findByRole("button", { name: "Layout…" }),
        );
        const one = await screen.findByRole("button", { name: "One viewport" });
        expect(screen.queryByRole("button", { name: "Layout…" })).toBeNull();
        expect(screen.getByRole("main")).not.toHaveAttribute("inert");
        await fireEvent.keyDown(one, { key: "Escape" });
        await waitFor(() => expect(menu).toHaveFocus());
    });

    it("below md loading an image into an empty viewport returns focus to the selected viewport", async () => {
        mockWidth({ md: false, xlg: false });
        const ws = workspaceWith(3, { layout: "2x1" });
        ws.close(1);
        ws.select(1);
        renderFrame(ws);
        const choose = screen.getByRole("button", { name: "Choose an image" });
        choose.focus();
        await fireEvent.click(choose);
        const panel = await screen.findByRole("region", { name: "Images" });
        await fireEvent.click(panel.querySelectorAll("li button")[2]);
        await waitFor(() =>
            expect(screen.getByRole("main")).not.toHaveAttribute("inert"),
        );
        await waitFor(() =>
            expect(
                document.querySelector('[aria-current="true"]'),
            ).toContainElement(document.activeElement as HTMLElement),
        );
    });
});
