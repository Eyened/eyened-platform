/** Enter turns on a cursor that arrows move and Space presses, for using pointer tools from the keyboard. */

export type CursorEventName = "pointerdown" | "pointermove" | "pointerup";

export interface KeyboardCursorHost {
    size(): { width: number; height: number };
    send(name: CursorEventName, event: PointerEvent): void;
    changed(on: boolean): void;
}

const ARROWS: Record<string, [number, number]> = {
    ArrowLeft: [-1, 0],
    ArrowRight: [1, 0],
    ArrowUp: [0, -1],
    ArrowDown: [0, 1],
};

export class KeyboardCursor {
    on = $state(false);
    position = { x: 0, y: 0 };
    host: KeyboardCursorHost | undefined;
    private pressed = false;

    keydown(event: KeyboardEvent): boolean {
        if (!this.host) return false;
        if (!this.on) {
            if (event.key !== "Enter" || event.repeat) return false;
            event.preventDefault();
            const { width, height } = this.host.size();
            this.on = true;
            this.position = {
                x: Math.round(width / 2),
                y: Math.round(height / 2),
            };
            this.host.changed(true);
            this.send("pointermove");
            return true;
        }
        if (event.key === "Enter") {
            event.preventDefault();
            return true;
        }
        const arrow = ARROWS[event.key];
        if (arrow) {
            event.preventDefault();
            const step = event.shiftKey ? 10 : 1;
            const { width, height } = this.host.size();
            this.position = {
                x: Math.min(
                    width - 1,
                    Math.max(0, this.position.x + arrow[0] * step),
                ),
                y: Math.min(
                    height - 1,
                    Math.max(0, this.position.y + arrow[1] * step),
                ),
            };
            this.send("pointermove");
            return true;
        }
        if (event.code === "Space") {
            event.preventDefault();
            if (!event.repeat && !this.pressed) {
                this.pressed = true;
                this.send("pointerdown");
            }
            return true;
        }
        return false;
    }

    /** Only a Space it pressed itself; a Space held for the mouse before Enter ends at the tool. */
    keyup(event: KeyboardEvent): boolean {
        if (!this.on || !this.pressed || event.code !== "Space") return false;
        this.release();
        return true;
    }

    /** Esc, blur and unmount end the mode; a held press is released first. */
    leave(): void {
        if (!this.on) return;
        this.release();
        this.on = false;
        this.host?.changed(false);
    }

    /** The mouse moves the same point. */
    follow(point: { x: number; y: number }): void {
        if (this.on) this.position = { ...point };
    }

    private release(): void {
        if (!this.pressed) return;
        this.pressed = false;
        this.send("pointerup");
    }

    private send(name: CursorEventName): void {
        this.host?.send(
            name,
            new PointerEvent(name, {
                button: name === "pointermove" ? -1 : 0,
                buttons: this.pressed ? 1 : 0,
                pointerId: 1,
                pointerType: "mouse",
                isPrimary: true,
            }),
        );
    }
}
