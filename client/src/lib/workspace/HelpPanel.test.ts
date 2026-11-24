import { fireEvent, render, screen, waitFor } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import HelpPanel from "./HelpPanel.svelte";
import { workspaceContext, workspaceWith } from "./testUtils";

const expanded = () =>
    [
        "View",
        "Measure",
        "Draw",
        "Place",
        "Viewport",
        "Images, layout and panels",
        "Keyboard cursor",
    ].filter(
        (name) =>
            screen
                .queryByRole("button", { name })
                ?.getAttribute("aria-expanded") === "true",
    );

describe("HelpPanel", () => {
    it("opens on the armed tool's group; a search opens every match and counts them; clearing it brings the open sections back", async () => {
        const ws = workspaceWith(1);
        ws.arm("brush");
        render(HelpPanel, {
            props: { shown: true },
            context: workspaceContext(ws),
        });
        await waitFor(() => expect(expanded()).toEqual(["Draw"]));

        const box = screen.getByRole("searchbox", { name: "Search keys" });
        await fireEvent.input(box, { target: { value: "space" } });
        expect(screen.getByText("6 results")).toBeInTheDocument();
        expect(expanded()).toEqual(["Draw", "Place", "Keyboard cursor"]);

        await fireEvent.keyDown(box, { key: "Escape" });
        expect(expanded()).toEqual(["Draw"]);
    });
});
