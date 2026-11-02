import { describe, expect, it } from "vitest";
import { cn, tv } from "./utils";

describe("class merging with Carbon type tokens", () => {
    it("cn keeps a type class next to a text colour class", () => {
        expect(cn("text-body-compact-01", "text-text-primary")).toBe(
            "text-body-compact-01 text-text-primary",
        );
    });

    it("tv keeps a type class next to a text colour class", () => {
        const variants = tv({ base: "text-body-compact-01" });
        expect(variants({ class: "text-text-primary" })).toBe(
            "text-body-compact-01 text-text-primary",
        );
    });
});
