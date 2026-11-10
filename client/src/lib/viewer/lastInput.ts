// Whether the last input was a pointer press or a key. Listeners attach on import.
let keyboard = false;

if (typeof window !== "undefined") {
    window.addEventListener("pointerdown", () => (keyboard = false), true);
    window.addEventListener("keydown", () => (keyboard = true), true);
}

export function lastInputWasKeyboard(): boolean {
    return keyboard;
}
