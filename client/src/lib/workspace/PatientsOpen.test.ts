import { render, screen } from "@testing-library/svelte";
import { describe, expect, it } from "vitest";
import PatientsOpen from "./PatientsOpen.svelte";
import { mockWidth } from "./testUtils";

describe("PatientsOpen", () => {
    it("with one patient the status region is there and empty", () => {
        mockWidth({ md: true, xlg: true });
        render(PatientsOpen, { props: { count: 1 } });
        expect(screen.getByRole("status")).toBeEmptyDOMElement();
    });

    it("below xlg shows the warning and the count, with the words in the status region and the button's name", () => {
        mockWidth({ md: true, xlg: false });
        render(PatientsOpen, { props: { count: 2 } });
        expect(screen.getByRole("status")).toHaveTextContent("2 patients open");
        expect(
            screen.getByRole("button", { name: "2 patients open" }),
        ).toHaveTextContent(/^2$/);
    });
});
