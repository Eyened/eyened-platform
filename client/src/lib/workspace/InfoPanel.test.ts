import { fireEvent, render, screen } from "@testing-library/svelte";
import { describe, expect, it, vi } from "vitest";
import InfoPanel from "./InfoPanel.svelte";
import { instance, workspaceContext, workspaceWith } from "./testUtils";

vi.mock("$lib/utils/copyToClipboard", () => ({
    copyToClipboard: vi.fn(async () => true),
}));

describe("InfoPanel", () => {
    it("copying a value says so in the panel's status; the button keeps its name", async () => {
        render(InfoPanel, {
            props: {
                instanceFor: (id: string) => instance(id),
                subtitle: "Viewport 1 · P-000417 OD · CF F1",
                shown: false,
            },
            context: workspaceContext(workspaceWith(1)),
        });
        await fireEvent.click(
            screen.getByRole("button", { name: "Copy Patient ID" }),
        );
        // By text: Visits' loading indicator may be a status region too.
        expect(await screen.findByText("Patient ID copied")).toHaveAttribute(
            "role",
            "status",
        );
        expect(
            screen.getByRole("button", { name: "Copy Patient ID" }),
        ).toBeInTheDocument();
    });
});
