import {
    cleanup,
    fireEvent,
    render,
    screen,
    waitFor,
    within,
} from "@testing-library/svelte";
import { createRawSnippet } from "svelte";
import {
    afterEach,
    beforeAll,
    beforeEach,
    describe,
    expect,
    it,
    vi,
} from "vitest";
import { DebouncedSaver } from "$lib/saving/debouncedSaver.svelte";
import { saveTracker } from "$lib/saving/saveTracker.svelte";
import {
    expectNoAxeViolations,
    instance,
    mockWidth,
    workspaceContext,
    workspaceWith,
} from "./testUtils";
import type { ResolvedPathname } from "$app/types";
import type { Workspace } from "./workspace.svelte";
import WorkspaceFrame from "./WorkspaceFrame.svelte";
import type { TaskHeader } from "./WorkspaceHeader.svelte";

// The Magnifier's viewer reaches cornerstone's WADO loader, which throws on import under jsdom.
vi.mock("cornerstone-wado-image-loader", () => ({
    external: {},
    configure: vi.fn(),
}));
vi.mock("cornerstone-core", () => ({}));
vi.mock("dicom-parser", () => ({}));

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
        overviewHref: "/tasks/7" as ResolvedPathname,
        show: { title: true, nav: true, overview: true },
        pending: null,
    };
}

function renderFrame(
    ws: Workspace,
    task: TaskHeader | null = null,
    extra: Record<string, unknown> = {},
) {
    return render(WorkspaceFrame, {
        props: {
            viewer,
            tile,
            titleFor,
            instanceFor: (id: string) => instance(id),
            onaddimages: vi.fn(),
            emptyMessage: null,
            task,
            ...extra,
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
        expect(screen.getByRole("button", { name: "Layers" })).toHaveAttribute(
            "aria-pressed",
            "false",
        );
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
        await fireEvent.click(screen.getByRole("button", { name: "Layers" }));
        expect(screen.getByRole("button", { name: "Layers" })).toHaveAttribute(
            "aria-pressed",
            "true",
        );
        cleanup();
        renderFrame(workspaceWith(3));
        expect(
            screen.getByRole("region", { name: "Info" }),
        ).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Layers" })).toHaveAttribute(
            "aria-pressed",
            "true",
        );
    });

    it("below md starts with the right column closed even when stored open, and has no icon columns", () => {
        localStorage.setItem("eyened:viewer:rightOpen", "true");
        mockWidth({ md: false, xlg: true });
        renderFrame(workspaceWith(3));
        expect(
            screen.queryByRole("navigation", { name: "Tools and panels" }),
        ).toBeNull();
        expect(screen.queryByRole("button", { name: "Layers" })).toBeNull();
        expect(screen.queryByRole("region", { name: "Layers" })).toBeNull();
        expect(screen.getByRole("main")).not.toHaveAttribute("inert");
    });

    it("below md the header button opens the right panel over inert regions; Esc returns focus; nothing is stored", async () => {
        mockWidth({ md: false, xlg: false });
        const { container } = renderFrame(workspaceWith(3), taskHeader());
        const button = screen.getByRole("button", {
            name: "Show Layers and Grading",
        });
        await fireEvent.click(button);
        expect(
            screen.getByRole("region", { name: "Grading" }),
        ).toBeInTheDocument();
        await waitFor(() =>
            expect(
                screen.getByRole("heading", { name: "Grading" }),
            ).toHaveFocus(),
        );
        for (const el of underOverlay(container))
            expect(el).toHaveAttribute("inert");
        expect(button).toHaveAccessibleName("Hide Layers and Grading");
        const panels = screen.getByRole("group", { name: "Panels" });
        const toLayers = within(panels).getByRole("button", {
            name: "Layers",
        });
        await fireEvent.click(toLayers);
        expect(
            screen.getByRole("region", { name: "Layers" }),
        ).toBeInTheDocument();
        expect(screen.queryByRole("region", { name: "Grading" })).toBeNull();
        await fireEvent.keyDown(toLayers, { key: "Escape" });
        await waitFor(() => expect(button).toHaveFocus());
        for (const el of underOverlay(container))
            expect(el).not.toHaveAttribute("inert");
        expect(localStorage.getItem("eyened:viewer:rightOpen")).toBeNull();
    });

    it("below md the menu holds Task overview, Layout…, the tools and Images; Esc closes it; nothing is stored", async () => {
        mockWidth({ md: false, xlg: false });
        const task = taskHeader();
        const { container } = renderFrame(workspaceWith(3), task);
        const menu = screen.getByRole("button", { name: "Show menu" });
        await fireEvent.click(menu);
        await waitFor(() =>
            expect(
                screen.getByRole("link", {
                    name: "Task overview, opens in a new tab",
                }),
            ).toHaveFocus(),
        );
        expect(menu).toHaveAccessibleName("Hide menu");
        expect(
            screen.getByRole("button", { name: "Layout…" }),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("toolbar", { name: "Tools" }),
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
        const overview = await screen.findByRole("link", {
            name: "Task overview, opens in a new tab",
        });
        // jsdom can't open a tab; the menu still closes.
        overview.addEventListener("click", (e) => e.preventDefault());
        await fireEvent.click(overview);
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
        await fireEvent.click(panel.querySelectorAll('[role="option"]')[2]);
        await waitFor(() =>
            expect(screen.getByRole("main")).not.toHaveAttribute("inert"),
        );
        await waitFor(() =>
            expect(
                document.querySelector('[aria-current="true"]'),
            ).toContainElement(document.activeElement as HTMLElement),
        );
    });

    it("crossing md closes an open overlay and moves focus to the button that now controls it", async () => {
        const width = mockWidth({ md: false, xlg: false });
        renderFrame(workspaceWith(3));
        await fireEvent.click(
            screen.getByRole("button", { name: "Show Layers and Forms" }),
        );
        await waitFor(() =>
            expect(
                screen.getByRole("heading", { name: "Layers" }),
            ).toHaveFocus(),
        );
        width.resize({ md: true, xlg: false });
        await waitFor(() =>
            expect(
                screen.getByRole("button", { name: "Layers" }),
            ).toHaveFocus(),
        );
        expect(screen.getByRole("main")).not.toHaveAttribute("inert");
        expect(screen.queryByRole("region", { name: "Layers" })).toBeNull();

        await fireEvent.click(screen.getByRole("button", { name: "Info" }));
        await waitFor(() =>
            expect(screen.getByRole("heading", { name: "Info" })).toHaveFocus(),
        );
        width.resize({ md: false, xlg: false });
        await waitFor(() =>
            expect(
                screen.getByRole("button", { name: "Show menu" }),
            ).toHaveFocus(),
        );
        expect(screen.queryByRole("region", { name: "Info" })).toBeNull();
        expect(localStorage.getItem("eyened:viewer:leftPanel")).toBe("info");
    });

    it("F1 opens Help, but not from a text field", async () => {
        mockWidth({ md: true, xlg: true });
        renderFrame(workspaceWith(2));
        const field = document.body.appendChild(
            document.createElement("input"),
        );
        await fireEvent.keyDown(field, { key: "F1" });
        expect(screen.queryByRole("region", { name: "Help" })).toBeNull();
        field.remove();
        await fireEvent.keyDown(document.body, { key: "F1" });
        expect(
            screen.getByRole("region", { name: "Help" }),
        ).toBeInTheDocument();
    });

    it("a second F1 keeps the first opener, so Esc returns focus there", async () => {
        mockWidth({ md: false, xlg: false });
        renderFrame(workspaceWith(3));
        const menu = screen.getByRole("button", { name: "Show menu" });
        menu.focus();
        await fireEvent.keyDown(document.body, { key: "F1" });
        const help = await screen.findByRole("region", { name: "Help" });
        await fireEvent.keyDown(document.body, { key: "F1" });
        await fireEvent.keyDown(help, { key: "Escape" });
        await waitFor(() => expect(menu).toHaveFocus());
    });

    it("F1 with a tool armed scrolls to its Help group after focusing the heading, so the focus doesn't scroll back up", async () => {
        mockWidth({ md: true, xlg: true });
        const ws = workspaceWith(2);
        ws.arm("brush");
        renderFrame(ws);
        const focusedAtScroll: (Element | null)[] = [];
        const original = Element.prototype.scrollIntoView;
        Element.prototype.scrollIntoView = function () {
            focusedAtScroll.push(document.activeElement);
        };
        try {
            await fireEvent.keyDown(document.body, { key: "F1" });
            const heading = await screen.findByRole("heading", {
                name: "Help",
            });
            await waitFor(() => expect(focusedAtScroll).toHaveLength(1));
            expect(focusedAtScroll[0]).toBe(heading);
        } finally {
            Element.prototype.scrollIntoView = original;
        }
    });

    it("at md, F1 from an Images option then Esc returns focus to the Help icon, not the Images one", async () => {
        mockWidth({ md: true, xlg: true });
        renderFrame(workspaceWith(2));
        await fireEvent.click(screen.getByRole("button", { name: "Images" }));
        const option = (await screen.findAllByRole("option")).find(
            (o) => o.tabIndex === 0,
        )!;
        option.focus();
        await fireEvent.keyDown(option, { key: "F1" });
        const heading = await screen.findByRole("heading", { name: "Help" });
        await fireEvent.keyDown(heading, { key: "Escape" });
        await waitFor(() =>
            expect(screen.getByRole("button", { name: "Help" })).toHaveFocus(),
        );
    });

    it("at md, Esc inside a left panel closes it and returns focus to where it was; Esc in a viewport leaves the panel open", async () => {
        mockWidth({ md: true, xlg: true });
        // With the strip on, Images starts closed.
        const ws = workspaceWith(2);
        ws.strip = false;
        renderFrame(ws);
        expect(
            screen.getByRole("region", { name: "Images" }),
        ).toBeInTheDocument();
        const control = document.querySelector<HTMLElement>(
            '[aria-current="true"] [tabindex="0"]',
        )!;
        control.focus();
        await fireEvent.keyDown(control, { key: "Escape" });
        expect(
            screen.getByRole("region", { name: "Images" }),
        ).toBeInTheDocument();

        await fireEvent.keyDown(control, { key: "F1" });
        const heading = await screen.findByRole("heading", { name: "Help" });
        await waitFor(() => expect(heading).toHaveFocus());
        // A right panel's icon pressed meanwhile is not where Esc returns.
        await fireEvent.click(screen.getByRole("button", { name: "Layers" }));
        const box = screen.getByRole("searchbox", { name: "Search keys" });
        box.focus();
        await fireEvent.input(box, { target: { value: "space" } });
        await fireEvent.keyDown(box, { key: "Escape" });
        expect(box).toHaveValue("");
        expect(
            screen.getByRole("region", { name: "Help" }),
        ).toBeInTheDocument();
        // A second F1 with focus inside Help keeps the original opener.
        heading.focus();
        await fireEvent.keyDown(heading, { key: "F1" });
        await fireEvent.keyDown(box, { key: "Escape" });
        await waitFor(() => expect(control).toHaveFocus());
        expect(screen.queryByRole("region", { name: "Help" })).toBeNull();
    });
});

describe("Right panels", () => {
    it("/view opens on Layers; Forms swaps it in; the shown panel's icon folds the column", async () => {
        mockWidth({ md: true, xlg: true });
        renderFrame(workspaceWith(3));
        const layers = screen.getByRole("button", { name: "Layers" });
        const forms = screen.getByRole("button", { name: "Forms" });
        expect(layers).toHaveAttribute("aria-pressed", "true");
        expect(
            screen.getByRole("region", { name: "Layers" }),
        ).toBeInTheDocument();
        expect(screen.queryByRole("region", { name: "Forms" })).toBeNull();

        await fireEvent.click(forms);
        expect(forms).toHaveAttribute("aria-pressed", "true");
        expect(layers).toHaveAttribute("aria-pressed", "false");
        expect(
            screen.getByRole("region", { name: "Forms" }),
        ).toBeInTheDocument();
        expect(screen.queryByRole("region", { name: "Layers" })).toBeNull();

        await fireEvent.click(forms);
        expect(forms).toHaveAttribute("aria-pressed", "false");
        expect(screen.queryByRole("region", { name: "Forms" })).toBeNull();
        expect(localStorage.getItem("eyened:viewer:rightOpen")).toBe("false");
    });

    it("the grade route opens on Grading", () => {
        mockWidth({ md: true, xlg: true });
        renderFrame(workspaceWith(3), taskHeader());
        expect(screen.getByRole("button", { name: "Grading" })).toHaveAttribute(
            "aria-pressed",
            "true",
        );
        expect(
            screen.getByRole("region", { name: "Grading" }),
        ).toBeInTheDocument();
        expect(screen.queryByRole("region", { name: "Layers" })).toBeNull();
    });
});

describe("Layers", () => {
    it("names the selected viewport under the heading", async () => {
        mockWidth({ md: true, xlg: true });
        const ws = workspaceWith(2, { layout: "1x2" });
        renderFrame(ws);
        // Info repeats the line in its hidden section.
        const layers = within(screen.getByRole("region", { name: "Layers" }));
        expect(
            layers.getByText("Viewport 1 · P-000417 OD · CF F1 · img01"),
        ).toBeInTheDocument();
        ws.select(1);
        expect(
            await layers.findByText("Viewport 2 · P-000417 OD · CF F1 · img02"),
        ).toBeInTheDocument();
    });
});

const footerTag = createRawSnippet(() => ({
    render: () => `<span>In progress</span>`,
}));
const footerStatus = createRawSnippet((layout: () => string) => ({
    render: () =>
        `<button data-set-control="primary" data-layout="${layout()}">Mark ready and next</button>`,
}));

describe("below md, the Grading footer", () => {
    // The tracker is page-wide; a saver left behind by a failing test would leak into the next.
    let failing: DebouncedSaver<number> | null = null;
    afterEach(() => {
        failing?.discard();
        failing?.dispose();
        failing = null;
        saveTracker.edited = false;
    });

    it("holds the status tag, the save state and the stacked combo button", async () => {
        mockWidth({ md: false, xlg: false });
        renderFrame(workspaceWith(1), {
            ...taskHeader(),
            tag: footerTag,
            status: footerStatus,
        });
        await fireEvent.click(
            screen.getByRole("button", { name: "Show Layers and Grading" }),
        );
        const footer = document.querySelector("[data-set-footer]")!;
        expect(
            within(footer as HTMLElement).getByText("In progress"),
        ).toBeInTheDocument();
        expect(footer.querySelector('[data-layout="stacked"]')).not.toBeNull();
    });

    it("isn't there when the task shows neither status nor move", async () => {
        mockWidth({ md: false, xlg: false });
        renderFrame(workspaceWith(1), taskHeader());
        expect(document.querySelector("[data-set-footer]")).toBeNull();
    });

    it("a save that failed puts a dot on the panels button and says what failed", async () => {
        mockWidth({ md: false, xlg: false });
        failing = new DebouncedSaver<number>({
            kind: "form",
            group: "form-annotation-1",
            target: { to: "focus", focus: () => {} },
            delay: 0,
            send: () => Promise.reject(new Error("offline")),
        });
        failing.edit(1);
        await failing.flush();
        renderFrame(workspaceWith(1), taskHeader());
        expect(
            screen.getByRole("button", {
                name: "Show Layers and Grading, 1 form couldn't save",
            }),
        ).toBeInTheDocument();
    });

    it("arriving from the footer opens Grading and focuses its button", async () => {
        mockWidth({ md: false, xlg: false });
        renderFrame(
            workspaceWith(1),
            { ...taskHeader(), tag: footerTag, status: footerStatus },
            { startOnGrading: true },
        );
        await waitFor(() =>
            expect(document.activeElement).toBe(
                document.querySelector(
                    '[data-set-footer] [data-set-control="primary"]',
                ),
            ),
        );
    });

    it("arriving with no footer button focuses the Grading heading", async () => {
        mockWidth({ md: false, xlg: false });
        renderFrame(workspaceWith(1), taskHeader(), { startOnGrading: true });
        await waitFor(() =>
            expect(document.activeElement).toBe(
                screen.getByRole("heading", { name: "Grading" }),
            ),
        );
    });

    it("the header counts every open patient, in view or not", () => {
        mockWidth({ md: true, xlg: true });
        renderFrame(workspaceWith(3, { layout: "1x1" }), null, {
            instanceFor: (id: string) =>
                instance(id, {
                    patient:
                        id === "img03"
                            ? { id: 2, identifier: "P-000502" }
                            : { id: 1, identifier: "P-000417" },
                }),
        });
        expect(screen.getByText("2 patients open")).toBeInTheDocument();
    });
});
