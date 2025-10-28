import type { Registration } from "$lib/registration/registration";
import type { Position, Position2D } from "$lib/types";
import type { Overlay, ViewerEvent } from "../viewer-utils";
import type { ViewerContext } from "../viewerContext.svelte";

const [C, I, O] = [1, 3, 6];
export type etdrsGridType = {
	image_instance_id: string;
	form_data: {
		fovea: { x: number; y: number };
		disc_edge: { x: number; y: number };
	};
};
export class ETDRSGridItemOverlay implements Overlay {
	lineWidth = 1;
	strokeStyle = "rgba(255,255,255, 1)";
	name: string = "ETRDR grid item";

	constructor(
		private readonly annotation: etdrsGridType,
		private readonly registration: Registration,
		private readonly settings: { radiusFraction: number },
	) {}

	keydown(_keyEvent: ViewerEvent<KeyboardEvent>) {}

	repaint(viewerContext: ViewerContext) {
		const { image, context2D } = viewerContext;

		const f = this.annotation.form_data?.fovea;
		const d = this.annotation.form_data?.disc_edge;
		const srcId = String(this.annotation.image_instance_id);

		if (!f || !d) return;

		const fovea = this.registration.mapPosition(srcId, image.image_id, {
			...f,
			index: 0,
		} as Position);
		const discEdge = this.registration.mapPosition(srcId, image.image_id, {
			...d,
			index: 0,
		} as Position);
		if (!fovea || !discEdge) return;

		this.paint(context2D, viewerContext, fovea, discEdge);
	}

	private paint(
		ctx: CanvasRenderingContext2D,
		viewerContext: ViewerContext,
		fovea: Position2D,
		diskBorder: Position2D,
	) {
		ctx.lineWidth = this.lineWidth;
		ctx.strokeStyle = this.strokeStyle;
		ctx.imageSmoothingEnabled = true;

		const p_fovea = viewerContext.imageToViewerCoordinates(fovea);
		const p_diskBorder = viewerContext.imageToViewerCoordinates(diskBorder);

		const dx = p_diskBorder.x - p_fovea.x;
		const dy = p_diskBorder.y - p_fovea.y;
		const pix_per_mm =
			(1 / 3) * this.settings.radiusFraction * Math.sqrt(dx * dx + dy * dy);

		for (const diameter of [C, I, O]) {
			const r = diameter / 2;
			ctx.beginPath();
			ctx.ellipse(
				p_fovea.x,
				p_fovea.y,
				r * pix_per_mm,
				r * pix_per_mm,
				0,
				0,
				2 * Math.PI,
			);
			ctx.stroke();
		}

		const r = 0.5 * Math.sqrt(2) * pix_per_mm;
		for (const sdx of [-1, 1]) {
			for (const sdy of [-1, 1]) {
				ctx.moveTo(p_fovea.x + 0.5 * sdx * r, p_fovea.y + 0.5 * sdy * r);
				ctx.lineTo(p_fovea.x + 3 * sdx * r, p_fovea.y + 3 * sdy * r);
				ctx.stroke();
			}
		}
	}
}
