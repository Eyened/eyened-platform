import { describe, expect, it } from "vitest";
import { KeyboardCursor, type CursorEventName } from "./keyboardCursor.svelte";

type Sent = { name: CursorEventName; button: number; buttons: number };

function setup() {
    const sent: Sent[] = [];
    const changes: boolean[] = [];
    const cursor = new KeyboardCursor();
    cursor.host = {
        size: () => ({ width: 100, height: 80 }),
        send: (name, e) =>
            sent.push({ name, button: e.button, buttons: e.buttons }),
        changed: (on) => changes.push(on),
    };
    return { cursor, sent, changes };
}

function key(
    key: string,
    init: Partial<KeyboardEventInit> & { code?: string } = {},
): KeyboardEvent {
    return new KeyboardEvent("keydown", {
        key,
        code: init.code ?? key,
        ...init,
    });
}

describe("KeyboardCursor", () => {
    it("Enter turns it on at the centre, once", () => {
        const { cursor, sent, changes } = setup();
        expect(cursor.keydown(key("Enter"))).toBe(true);
        expect(cursor.on).toBe(true);
        expect(cursor.position).toEqual({ x: 50, y: 40 });
        expect(sent.map((s) => s.name)).toEqual(["pointermove"]);
        expect(changes).toEqual([true]);
        cursor.keydown(key("Enter"));
        expect(sent).toHaveLength(1);
        expect(changes).toHaveLength(1);
    });

    it("leaves every key alone while off", () => {
        const { cursor, sent } = setup();
        for (const k of ["ArrowUp", "ArrowLeft", " "]) {
            expect(
                cursor.keydown(key(k, { code: k === " " ? "Space" : k })),
            ).toBe(false);
        }
        expect(sent).toEqual([]);
    });

    it("takes the arrows, Up and Down too: 1 px, Shift 10 px, stopping at the edges", () => {
        const { cursor } = setup();
        cursor.keydown(key("Enter"));
        expect(cursor.keydown(key("ArrowRight"))).toBe(true);
        expect(cursor.keydown(key("ArrowDown", { shiftKey: true }))).toBe(true);
        expect(cursor.position).toEqual({ x: 51, y: 50 });
        for (let i = 0; i < 10; i++)
            cursor.keydown(key("ArrowRight", { shiftKey: true }));
        for (let i = 0; i < 10; i++)
            cursor.keydown(key("ArrowUp", { shiftKey: true }));
        expect(cursor.position).toEqual({ x: 99, y: 0 });
    });

    it("Space is a left press; arrows between down and up drag", () => {
        const { cursor, sent } = setup();
        cursor.keydown(key("Enter"));
        sent.length = 0;
        expect(cursor.keydown(key(" ", { code: "Space" }))).toBe(true);
        cursor.keydown(key(" ", { code: "Space", repeat: true }));
        cursor.keydown(key("ArrowRight"));
        expect(
            cursor.keyup(
                new KeyboardEvent("keyup", { key: " ", code: "Space" }),
            ),
        ).toBe(true);
        expect(sent).toEqual([
            { name: "pointerdown", button: 0, buttons: 1 },
            { name: "pointermove", button: -1, buttons: 1 },
            { name: "pointerup", button: 0, buttons: 0 },
        ]);
    });

    it("leaves Esc to the keymap", () => {
        const { cursor } = setup();
        cursor.keydown(key("Enter"));
        expect(cursor.keydown(key("Escape"))).toBe(false);
        expect(cursor.on).toBe(true);
    });

    it("leave() releases a held press, then turns off", () => {
        const { cursor, sent, changes } = setup();
        cursor.keydown(key("Enter"));
        cursor.keydown(key(" ", { code: "Space" }));
        sent.length = 0;
        cursor.leave();
        expect(sent.map((s) => s.name)).toEqual(["pointerup"]);
        expect(cursor.on).toBe(false);
        expect(changes).toEqual([true, false]);
    });

    it("leaves a Space keyup it didn't press to the tools", () => {
        const { cursor, sent } = setup();
        cursor.keydown(key("Enter"));
        sent.length = 0;
        expect(
            cursor.keyup(
                new KeyboardEvent("keyup", { key: " ", code: "Space" }),
            ),
        ).toBe(false);
        expect(sent).toEqual([]);
    });
});
