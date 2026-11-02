import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/svelte";
import type { ImageGET } from "../../types/openapi_types";
import { instances } from "$lib/data/stores.svelte";
import InstanceInfo from "./InstanceInfo.svelte";

describe("InstanceInfo", () => {
    it("copies a property value", async () => {
        const writeText = vi.fn(() => Promise.resolve());
        Object.assign(navigator, { clipboard: { writeText } });
        instances.set("1.2.3", {
            id: "1.2.3",
            modality: "ColorFundus",
            tags: [],
        } as unknown as ImageGET);
        render(InstanceInfo, { props: { instanceId: "1.2.3" } });

        await fireEvent.click(
            screen.getByRole("button", { name: "Copy modality" }),
        );

        expect(writeText).toHaveBeenCalledWith("ColorFundus");
    });
});
