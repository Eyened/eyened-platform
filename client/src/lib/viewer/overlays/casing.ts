// A dark casing keeps overlay lines and text at 3:1 or more on a bright fundus or the optic disc.
const CASING = "rgba(0, 0, 0, 0.6)";

/** Runs `stroke` twice: as a solid casing 2 px wider, then with the current width, colour and dash. */
export function cased(
    ctx: CanvasRenderingContext2D,
    stroke: () => void,
    casing = CASING,
): void {
    const { lineWidth, strokeStyle } = ctx;
    const dash = ctx.getLineDash();
    ctx.lineWidth = lineWidth + 2;
    ctx.strokeStyle = casing;
    ctx.setLineDash([]);
    stroke();
    ctx.lineWidth = lineWidth;
    ctx.strokeStyle = strokeStyle;
    ctx.setLineDash(dash);
    stroke();
}

/** Fills text over a 3 px dark outline. */
export function casedText(
    ctx: CanvasRenderingContext2D,
    text: string,
    x: number,
    y: number,
    casing = CASING,
): void {
    const { lineWidth, strokeStyle, lineJoin } = ctx;
    const dash = ctx.getLineDash();
    ctx.setLineDash([]);
    ctx.lineWidth = 3;
    ctx.strokeStyle = casing;
    ctx.lineJoin = "round";
    ctx.strokeText(text, x, y);
    ctx.lineWidth = lineWidth;
    ctx.strokeStyle = strokeStyle;
    ctx.lineJoin = lineJoin;
    ctx.setLineDash(dash);
    ctx.fillText(text, x, y);
}
