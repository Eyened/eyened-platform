import { fireEvent, render, screen } from "@testing-library/svelte";
import { beforeEach, describe, expect, it, vi } from "vitest";

const webgl = vi.hoisted(() => ({ works: true }));

vi.mock("$lib/webgl/webgl", () => ({
    WebGL: class {
        gl = { getExtension: () => null };
        constructor() {
            // As the real class does when the browser gives no WebGL 2 context.
            if (!webgl.works) throw new Error("WebGL 2 is not available");
        }
    },
}));
vi.mock("$lib/registration/registration.svelte", () => ({
    Registration: class {},
}));
vi.mock("./viewerWindowContext.svelte", () => ({
    ViewerWindowContext: class {
        destroy() {}
    },
}));
vi.mock("./ViewerWindow.svelte", async () => ({
    default: (await import("./ViewerWindowStub.svelte")).default,
}));

const { default: ViewerWindowLoader } = await import(
    "./ViewerWindowLoader.svelte"
);

function renderLoader() {
    return render(ViewerWindowLoader, {
        props: { instanceIDs: ["inst-1"] },
        context: new Map([["globalContext", { user: { id: 1 } }]]),
    });
}

beforeEach(() => {
    webgl.works = true;
    vi.spyOn(console, "error").mockImplementation(() => {});
});

describe("ViewerWindowLoader", () => {
    it("without WebGL 2 says the viewer can't start, instead of a blank page", async () => {
        webgl.works = false;
        renderLoader();
        expect(
            await screen.findByText("The viewer can't start"),
        ).toBeInTheDocument();
    });

    it("a lost context unmounts the window and offers Reload page", async () => {
        const { container } = renderLoader();
        expect(await screen.findByText("Viewer window")).toBeInTheDocument();

        await fireEvent(
            container.querySelector("canvas")!,
            new Event("webglcontextlost", { cancelable: true }),
        );

        expect(screen.queryByText("Viewer window")).toBeNull();
        expect(screen.getByText("The viewer stopped")).toBeInTheDocument();
        await vi.waitFor(() =>
            expect(
                screen.getByRole("button", { name: "Reload page" }),
            ).toHaveFocus(),
        );
    });
});
