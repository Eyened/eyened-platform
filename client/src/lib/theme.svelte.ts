import { MediaQuery } from "svelte/reactivity";

export type ThemeChoice = "system" | "light" | "dark";
export type Theme = "light" | "dark";

const STORAGE_KEY = "eyened:theme";

// The viewer and grading pages stay dark in every theme. The first-paint script in app.html uses the same pattern.
const VIEWER_PATH = /^\/(view|tasks\/[^/]+\/grade\/[^/]+)\/?$/;

export function readThemeChoice(): ThemeChoice {
    try {
        const value = localStorage.getItem(STORAGE_KEY);
        return value === "light" || value === "dark" ? value : "system";
    } catch {
        return "system";
    }
}

export function resolveTheme(
    choice: ThemeChoice,
    osPrefersLight: boolean,
    pathname: string,
): Theme {
    if (VIEWER_PATH.test(pathname)) return "dark";
    if (choice === "system") return osPrefersLight ? "light" : "dark";
    return choice;
}

// The user's choice, saved per browser, and the OS preference it falls back to.
class ThemeState {
    #choice = $state(readThemeChoice());
    #osPrefersLight = new MediaQuery("(prefers-color-scheme: light)");

    get choice(): ThemeChoice {
        return this.#choice;
    }

    set choice(value: ThemeChoice) {
        this.#choice = value;
        try {
            localStorage.setItem(STORAGE_KEY, value);
        } catch {
            // Storage blocked: the choice lasts until the page reloads.
        }
    }

    forPath(pathname: string): Theme {
        return resolveTheme(
            this.#choice,
            this.#osPrefersLight.current,
            pathname,
        );
    }
}

export const theme = new ThemeState();
