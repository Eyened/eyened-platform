import { describe, expect, it, vi } from "vitest";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import type { ViewerContext } from "../viewerContext.svelte";
import type { ViewerEvent } from "../viewer-utils";
import { UpdatePosition } from "./updatePosition";

function makeEvent({
    shift,
    buttons = 0,
    updatePosition = true,
    isTopViewer = false,
}: {
    shift: boolean;
    buttons?: number;
    updatePosition?: boolean;
    isTopViewer?: boolean;
}) {
    const setPosition = vi.fn();
    const image = { image_id: "img-1" } as AbstractImage;
    const viewerContext = {
        updatePosition,
        index: 7,
        image,
        registration: { setPosition },
        viewerToImageCoordinates: () => ({ x: 3, y: 4 }),
        viewerWindowContext: {
            topViewers: {
                get: (img: AbstractImage) =>
                    isTopViewer && img === image ? viewerContext : undefined,
            },
        },
    } as unknown as ViewerContext;
    const event = {
        event: { buttons } as PointerEvent,
        cursor: { x: 10, y: 20 },
        position: { x: 3, y: 4 },
        modifiers: { shift, ctrl: false, alt: false, meta: false },
        viewerContext,
    } as ViewerEvent<PointerEvent>;
    return { event, setPosition };
}

describe("UpdatePosition", () => {
    const control = new UpdatePosition();

    it("updates the linked cursor on hover in the main viewer", () => {
        const { event, setPosition } = makeEvent({ shift: false });
        control.pointermove(event);
        expect(setPosition).toHaveBeenCalledWith("img-1", {
            x: 3,
            y: 4,
            index: 7,
        });
    });

    it("updates the linked cursor on main-viewer hover while Shift is held", () => {
        const { event, setPosition } = makeEvent({ shift: true });
        control.pointermove(event);
        expect(setPosition).toHaveBeenCalledWith("img-1", {
            x: 3,
            y: 4,
            index: 7,
        });
    });

    it("does not update the linked cursor on top-row hover without Shift", () => {
        const { event, setPosition } = makeEvent({
            shift: false,
            isTopViewer: true,
        });
        control.pointermove(event);
        expect(setPosition).not.toHaveBeenCalled();
    });

    it("updates the linked cursor on top-row hover while Shift is held", () => {
        const { event, setPosition } = makeEvent({
            shift: true,
            isTopViewer: true,
        });
        control.pointermove(event);
        expect(setPosition).toHaveBeenCalledWith("img-1", {
            x: 3,
            y: 4,
            index: 7,
        });
    });

    it("does not update the linked cursor while dragging a top-row viewer", () => {
        const { event, setPosition } = makeEvent({
            shift: true,
            buttons: 1,
            isTopViewer: true,
        });
        control.pointermove(event);
        expect(setPosition).not.toHaveBeenCalled();
    });
});
