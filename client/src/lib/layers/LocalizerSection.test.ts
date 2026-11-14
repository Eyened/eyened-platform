import { cleanup, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { PhotoLocator } from "$lib/registration/photoLocators";
import { expectNoAxeViolations } from "$lib/workspace/testUtils";
import LocalizerSection from "./LocalizerSection.svelte";
import { LocalizerLines } from "./localizerLines.svelte";

afterEach(() => {
    cleanup();
    localStorage.clear();
});

/** Two B-scan lines of oct-1 and one of oct-2 on this image. */
const locators = () =>
    ["oct-1", "oct-1", "oct-2"].map(
        (octImageId) => ({ octImageId }) as PhotoLocator,
    );

describe("LocalizerSection", () => {
    it("lists each OCT once with its line count, and passes axe", async () => {
        const { container } = render(LocalizerSection, {
            props: {
                localizer: new LocalizerLines(locators),
                open: true,
                ontoggle: vi.fn(),
            },
        });
        expect(
            screen.getAllByRole("listitem").map((li) => li.textContent),
        ).toEqual(["OCT oct-1 · 2 B-scans", "OCT oct-2 · 1 B-scans"]);
        await expectNoAxeViolations(container);
    });
});
