import axe from "axe-core";
import { expect, vi } from "vitest";
import { Workspace } from "./workspace.svelte";
import type { CatalogueEntry } from "./workspaceRules";
import type { WorkspaceUrlState } from "./workspaceUrl";

/** A synthetic catalogue entry. */
export function entry(
    imageId: string,
    over: Partial<CatalogueEntry> = {},
): CatalogueEntry {
    return {
        imageId,
        patient: "P-000417",
        date: "2023-05-04",
        modalityRank: 0,
        eyeRank: 0,
        ...over,
    };
}

/** n images of one patient and visit, ids img01, img02, … in that order. */
export function entries(n: number): CatalogueEntry[] {
    return Array.from({ length: n }, (_, i) =>
        entry(`img${String(i + 1).padStart(2, "0")}`, { modalityRank: i }),
    );
}

export const NO_URL: WorkspaceUrlState = {
    v: [],
    layout: null,
    page: 1,
    arrange: "opened",
};

export function workspaceWith(
    n: number,
    url: Partial<WorkspaceUrlState> = {},
    writeUrl: (state: WorkspaceUrlState) => void = () => {},
): Workspace {
    const workspace = new Workspace({ writeUrl });
    workspace.hydrate(entries(n), { ...NO_URL, ...url });
    return workspace;
}

export function workspaceContext(workspace: Workspace): Map<string, unknown> {
    return new Map([["workspace", workspace]]);
}

/** axe on a rendered fragment; jsdom can't compute contrast and fragments have no landmarks. */
export async function expectNoAxeViolations(container: Element): Promise<void> {
    const results = await axe.run(container, {
        rules: {
            "color-contrast": { enabled: false },
            region: { enabled: false },
        },
    });
    expect(
        results.violations.map((v) => `${v.id}: ${v.nodes[0]?.html}`),
    ).toEqual([]);
}

/** Makes svelte's MediaQuery see a window at least `md` and/or `xlg` wide; `resize` changes it and fires `change`. */
export function mockWidth(widths: { md: boolean; xlg: boolean }) {
    const current = { ...widths };
    const listeners = new Set<(e: Event) => void>();
    const matches = (query: string) =>
        query.includes("82rem")
            ? current.xlg
            : query.includes("42rem")
              ? current.md
              : false;
    const spy = vi.spyOn(window, "matchMedia").mockImplementation(
        (query: string) =>
            ({
                get matches() {
                    return matches(query);
                },
                media: query,
                onchange: null,
                addEventListener: (
                    _type: string,
                    listener: (e: Event) => void,
                ) => listeners.add(listener),
                removeEventListener: (
                    _type: string,
                    listener: (e: Event) => void,
                ) => listeners.delete(listener),
                addListener: () => {},
                removeListener: () => {},
                dispatchEvent: () => false,
            }) as unknown as MediaQueryList,
    );
    return Object.assign(spy, {
        resize(next: { md: boolean; xlg: boolean }) {
            Object.assign(current, next);
            // Svelte's event wrapper reads event.type, so pass a real Event.
            for (const listener of listeners) listener(new Event("change"));
        },
    });
}
