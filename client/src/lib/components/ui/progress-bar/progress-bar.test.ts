import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import ProgressBar from "./progress-bar.svelte";

describe("ProgressBar", () => {
    it("fills the bar and shows the checkmark when finished", () => {
        const { container } = render(ProgressBar, {
            props: {
                labelText: "Upload",
                value: 3,
                max: 4,
                status: "finished",
            },
        });
        expect(screen.getByRole("progressbar")).toHaveAttribute(
            "aria-valuenow",
            "4",
        );
        expect(
            container.querySelector('[data-slot="progress-bar-status-icon"]'),
        ).not.toBeNull();
    });
});
