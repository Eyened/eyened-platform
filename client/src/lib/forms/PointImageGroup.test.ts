import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/svelte";
import PointImageGroup from "./PointImageGroup.svelte";

const group = {
    publicId: "img-abc",
    rows: [
        { publicId: "img-abc", index: 0, pt: { x: 1, y: 2 } },
        { publicId: "img-abc", index: 1, pt: { x: 3, y: 4, note: "n" } },
    ],
};

describe("PointImageGroup", () => {
    it("renders rows under the image heading and expands an editor", async () => {
        const onGoTo = vi.fn();
        const onRemovePoint = vi.fn();
        const onCollapse = vi.fn();

        render(PointImageGroup, {
            props: {
                group,
                heading: "OD · CF · 2024-03-12",
                expandedKey: "img-abc:1",
                canEdit: true,
                hasExtras: true,
                enumExtras: [],
                stringExtraKeys: ["note"],
                rowKey: (row) => `${row.publicId}:${row.index}`,
                bscanText: () => null,
                extraPreview: (pt) =>
                    typeof pt.note === "string" ? ` ${pt.note}` : "",
                indexApplicable: () => false,
                onGoTo,
                hint: null,
                onUpdateCoord: vi.fn(),
                onUpdateExtra: vi.fn(),
                onRemovePoint,
                onCollapse,
            },
        });

        expect(screen.getByTitle("img-abc")).toHaveTextContent(
            "OD · CF · 2024-03-12",
        );
        expect(screen.getByText("2 points")).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: /^Point2 x3 y4/ }),
        ).toHaveAttribute("aria-expanded", "true");
        expect(
            screen.getByRole("group", { name: "Point 2" }),
        ).toBeInTheDocument();

        await fireEvent.click(
            screen.getByRole("button", { name: /^Point1 x1/ }),
        );
        expect(onGoTo).toHaveBeenCalledWith({
            publicId: "img-abc",
            index: 0,
            pt: { x: 1, y: 2 },
        });

        await fireEvent.click(
            screen.getByRole("button", { name: "Delete point" }),
        );
        expect(onRemovePoint).toHaveBeenCalledWith("img-abc", 1);

        await fireEvent.click(screen.getByRole("button", { name: "Done" }));
        expect(onCollapse).toHaveBeenCalled();
    });
});
