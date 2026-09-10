import { describe, it, expect, beforeEach, vi } from "vitest";
import { FormPointSession, pointArming } from "./pointArming.svelte";
import type { PointSchemaAnalysis } from "./pointSchema";

const analysis: PointSchemaAnalysis = {
    cardinality: "list",
    addressing: "bare",
    pointObjectSchema: { type: "object" },
    sparse: false,
    enumExtras: [],
    coordinateSpace: "enface2d",
};

function makeSession(
    key: string,
    setFieldValue = vi.fn(),
    initialValue: unknown = [{ x: 1, y: 2 }],
) {
    return new FormPointSession({
        key,
        canEdit: true,
        pointStyle: "circle",
        radius: 8,
        color: "#0f0",
        analysis,
        initialValue,
        setFieldValue,
    });
}

describe("FormPointSession", () => {
    it("reads and writes points for an image", () => {
        const session = makeSession("f1");
        expect(session.getPoints("img")).toEqual([{ x: 1, y: 2 }]);
        session.setPoints("img", [{ x: 3, y: 4 }]);
        expect(session.getPoints("img")).toEqual([{ x: 3, y: 4 }]);
    });

    it("persist writes the live value into the form", () => {
        const setFieldValue = vi.fn();
        const session = makeSession("f1", setFieldValue);
        session.persist();
        expect(setFieldValue).toHaveBeenCalledWith([{ x: 1, y: 2 }]);
    });
});

describe("pointArming", () => {
    beforeEach(() => {
        pointArming.session = null;
    });

    it("arms a session", () => {
        const session = makeSession("a");
        pointArming.arm(session);
        expect(pointArming.isArmed("a")).toBe(true);
        expect(pointArming.session).toBe(session);
    });

    it("disarms the same key on a second arm", () => {
        const persist = vi.fn();
        const session = makeSession("a", persist);
        pointArming.arm(session);
        pointArming.arm(session);
        expect(pointArming.session).toBeNull();
        expect(persist).toHaveBeenCalled();
    });

    it("persists the previous session when switching keys", () => {
        const persistA = vi.fn();
        const persistB = vi.fn();
        pointArming.arm(makeSession("a", persistA));
        pointArming.arm(makeSession("b", persistB));
        expect(pointArming.isArmed("b")).toBe(true);
        expect(persistA).toHaveBeenCalled();
    });

    it("disarm is a no-op for a different key", () => {
        pointArming.arm(makeSession("a"));
        pointArming.disarm("other");
        expect(pointArming.isArmed("a")).toBe(true);
    });

    it("disarm clears the armed session", () => {
        const persist = vi.fn();
        pointArming.arm(makeSession("a", persist));
        pointArming.disarm("a");
        expect(pointArming.session).toBeNull();
        expect(persist).toHaveBeenCalled();
    });
});
