import { afterEach, describe, expect, it, vi } from "vitest";
import appHtml from "../app.html?raw";
import { readThemeChoice, resolveTheme } from "./theme.svelte";

// stored: the saved choice (null when nothing is saved); osLight: the OS prefers light.
const CASES = [
    { stored: null, osLight: false, path: "/library", expected: "dark" },
    { stored: null, osLight: true, path: "/", expected: "light" },
    { stored: "system", osLight: true, path: "/admin", expected: "light" },
    { stored: "light", osLight: false, path: "/tasks", expected: "light" },
    { stored: "dark", osLight: true, path: "/tasks/3", expected: "dark" },
    { stored: "blue", osLight: true, path: "/library", expected: "light" },
    { stored: "light", osLight: true, path: "/view", expected: "dark" },
    {
        stored: "light",
        osLight: true,
        path: "/tasks/3/grade/1",
        expected: "dark",
    },
    { stored: "light", osLight: true, path: "/viewer", expected: "light" },
] as const;

afterEach(() => {
    localStorage.clear();
    vi.unstubAllGlobals();
    history.replaceState(null, "", "/");
    delete document.documentElement.dataset.theme;
});

function store(value: string | null) {
    if (value !== null) localStorage.setItem("eyened:theme", value);
}

describe("resolveTheme", () => {
    it.each(CASES)(
        "$stored, OS light $osLight, $path → $expected",
        ({ stored, osLight, path, expected }) => {
            store(stored);
            expect(resolveTheme(readThemeChoice(), osLight, path)).toBe(
                expected,
            );
        },
    );
});

describe("app.html first-paint script", () => {
    const script = appHtml.match(
        /<script>([^<]*eyened:theme[^<]*)<\/script>/,
    )?.[1];

    it.each(CASES)(
        "$stored, OS light $osLight, $path → $expected",
        ({ stored, osLight, path, expected }) => {
            store(stored);
            history.replaceState(null, "", path);
            vi.stubGlobal("matchMedia", () => ({ matches: osLight }));

            new Function(script ?? "")();

            expect(document.documentElement.dataset.theme).toBe(expected);
        },
    );
});
