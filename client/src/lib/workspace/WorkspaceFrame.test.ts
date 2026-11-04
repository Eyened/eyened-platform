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

function renderFrame(ws: Workspace) {
    return render(WorkspaceFrame, {
        props: {
            viewer,
            tile,
            titleFor,
            onaddimages: vi.fn(),
            emptyMessage: null,
        },
        context: workspaceContext(ws),
    });
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

    it("below md opens a panel over an inert canvas and focuses it; Esc closes it and returns focus", async () => {
        mockWidth({ md: false, xlg: false });
        renderFrame(workspaceWith(3));
        expect(screen.queryByRole("region", { name: "Images" })).toBeNull();
        const images = screen.getByRole("button", { name: "Images" });
        await fireEvent.click(images);
        expect(screen.getByRole("main")).toHaveAttribute("inert");
        await waitFor(() =>
            expect(
                screen.getByRole("heading", { name: "Images" }),
            ).toHaveFocus(),
        );
        await fireEvent.keyDown(
            screen.getByRole("region", { name: "Images" }),
            {
                key: "Escape",
            },
        );
        await waitFor(() => expect(images).toHaveFocus());
        expect(screen.getByRole("main")).not.toHaveAttribute("inert");
    });
});
