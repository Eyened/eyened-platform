import { cleanup, fireEvent, render, screen } from "@testing-library/svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { expectNoAxeViolations } from "$lib/workspace/testUtils";
import SliderField from "./slider-field.svelte";

afterEach(cleanup);

describe("SliderField", () => {
    it("the value field commits a typed value, clamps one out of range and reverts one it cannot read", async () => {
        const onchange = vi.fn();
        const oncommit = vi.fn();
        const { container } = render(SliderField, {
            props: {
                labelText: "Threshold",
                value: 0.5,
                onchange,
                oncommit,
                min: 0,
                max: 1,
                step: 0.01,
                decimals: 2,
            },
        });
        expect(
            screen.getByRole("slider", { name: "Threshold" }),
        ).toBeInTheDocument();
        const field = screen.getByRole("spinbutton", { name: "Threshold" });
        expect(field).toHaveValue(0.5);

        await fireEvent.input(field, { target: { value: "0.7" } });
        await fireEvent.change(field);
        expect(onchange).toHaveBeenLastCalledWith(0.7);
        expect(oncommit).toHaveBeenCalledTimes(1);

        await fireEvent.input(field, { target: { value: "3" } });
        await fireEvent.keyDown(field, { key: "Enter" });
        expect(onchange).toHaveBeenLastCalledWith(1);
        expect(field).toHaveValue(1);

        await fireEvent.input(field, { target: { value: "" } });
        await fireEvent.change(field);
        expect(onchange).toHaveBeenCalledTimes(2);
        expect(field).toHaveValue(0.5);

        await expectNoAxeViolations(container);
    });
});
