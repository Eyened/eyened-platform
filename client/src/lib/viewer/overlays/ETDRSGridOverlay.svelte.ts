import type { Position2D } from "$lib/types";
import type { Overlay, ViewerEvent } from "../viewer-utils";
import type { Registration } from "$lib/registration/registration";
import type { ViewerContext } from "../viewerContext.svelte";
import type { RenderTarget } from "$lib/webgl/types";
import { SvelteSet } from "svelte/reactivity";
import type { Instance } from "$lib/datamodel/instance.svelte";

const [C, I, O] = [1, 3, 6];
const additionalCircles = {
	C0: C / 16,
	C1: C / 8,
	C2: C / 4,
	I1: I / 8,
	I2: I / 4,
	O1: O / 8,
	O2: O / 4
};

type CircleName = 'C0' | 'C1' | 'C2' | 'I1' | 'I2' | 'O1' | 'O2';

export interface etdrsFormAnnotationType {
	instance?: Instance;
	value: {
		value: {
			fovea: Position2D;
			disc_edge: Position2D;
		};
	};
}
export class ETDRSGridOverlay implements Overlay {

	public radiusFraction = $state(0.85);
	lineWidth = 1;
	strokeStyle = 'rgba(255,255,255, 1)';
	cursorCircle: CircleName | undefined = undefined;
	name: string = 'ETRDR grid';
	visible = new SvelteSet<etdrsFormAnnotationType>();

	constructor(private readonly registration: Registration) { }

	keydown(keyEvent: ViewerEvent<KeyboardEvent>) {
		const { event } = keyEvent;
		const circles: Record<string, CircleName[]> = {
			C: ['C0', 'C1', 'C2'],
			I: ['I1', 'I2'],
			O: ['O1', 'O2'],
		};
		const cycle = circles[event.key.toUpperCase()];
		if (cycle !== undefined) {
			const i = this.cursorCircle ? cycle.indexOf(this.cursorCircle) : 0;
			this.cursorCircle = cycle[(i + 1) % cycle.length];
		} else {
			this.cursorCircle = undefined;
		}
	}

	repaint(viewerContext: ViewerContext, renderTarget: RenderTarget) {
		const { image, context2D } = viewerContext;

		for (const formAnnotation of this.visible) {

			let image_id = `${formAnnotation.instance!.id}`;
			if (formAnnotation.instance!.nrOfFrames > 1) {
				// this is a hack to identify that it's a projection of a 3D image
				image_id = `${formAnnotation.instance!.id}_proj`;
			}

			const grid = formAnnotation.value.value;
			if (grid?.fovea && grid?.disc_edge) {
				const fovea = this.registration.mapPosition(
					image_id,
					image.image_id,
					{ ...grid.fovea, index: 0 }
				);
				const discEdge = this.registration.mapPosition(
					image_id,
					image.image_id,
					{ ...grid.disc_edge, index: 0 }
				);

				if (fovea && discEdge) {
					this.paint(context2D, viewerContext, fovea, discEdge);
				}
			}
		}
	}

	paint(ctx: CanvasRenderingContext2D, viewerContext: ViewerContext, fovea: Position2D, diskBorder: Position2D) {

		ctx.lineWidth = this.lineWidth;
		ctx.strokeStyle = this.strokeStyle;
		ctx.fillStyle = this.strokeStyle;
		ctx.font = '14px Arial';
		ctx.imageSmoothingEnabled = true;

		const p_fovea = viewerContext.imageToViewerCoordinates(fovea);
		const p_diskBorder = viewerContext.imageToViewerCoordinates(diskBorder);

		const dx = p_diskBorder.x - p_fovea.x;
		const dy = p_diskBorder.y - p_fovea.y;
		const pix_per_mm = (1 / 3) * this.radiusFraction * Math.sqrt(dx * dx + dy * dy);

		for (const diameter of [C, I, O]) {
			const r = diameter / 2;
			ctx.beginPath();
			ctx.ellipse(p_fovea.x, p_fovea.y, r * pix_per_mm, r * pix_per_mm, 0, 0, 2 * Math.PI);
			ctx.stroke();
		}

		const r = 0.5 * Math.sqrt(2) * pix_per_mm;
		for (const dx of [-1, 1]) {
			for (const dy of [-1, 1]) {
				ctx.moveTo(p_fovea.x + 0.5 * dx * r, p_fovea.y + 0.5 * dy * r);
				ctx.lineTo(p_fovea.x + 3 * dx * r, p_fovea.y + 3 * dy * r);
				ctx.stroke();
			}
		}

		const r_max = 0.5 * additionalCircles['O2'] * pix_per_mm;
		let y = viewerContext.viewerSize.height - 10 - r_max;
		let x = 10;
		if (r_max < 0.1 * viewerContext.viewerSize.height) {
			for (const [name, diameter] of Object.entries(additionalCircles)) {
				if (name == this.cursorCircle) {
					ctx.lineWidth = 4 * this.lineWidth;
					ctx.strokeStyle = 'rgba(100, 255, 100, 1)';
				} else {
					ctx.lineWidth = this.lineWidth;
					ctx.strokeStyle = this.strokeStyle;
				}
				const r = diameter / 2;
				x += r * pix_per_mm;
				ctx.beginPath();
				ctx.ellipse(x, y, r * pix_per_mm, r * pix_per_mm, 0, 0, 2 * Math.PI);
				ctx.stroke();
				ctx.fillText(name, x, y - r_max - 5);

				x += Math.max(r * pix_per_mm, 20);
				x += 10;
			}
		}
		// const cursor = this.registration.pointer[viewerContext.image.image_id];
		const cursor = this.registration.getPosition(viewerContext.image.image_id);
		if (cursor && this.cursorCircle) {
			ctx.lineWidth = this.lineWidth;
			ctx.strokeStyle = this.strokeStyle;
			const diameter = additionalCircles[this.cursorCircle];
			const r = diameter / 2;
			const { x, y } = viewerContext.imageToViewerCoordinates(cursor);
			ctx.beginPath();
			ctx.ellipse(x, y, r * pix_per_mm, r * pix_per_mm, 0, 0, 2 * Math.PI);
			ctx.stroke();
			viewerContext.cursorStyle = 'none';
		} else {
			viewerContext.cursorStyle = 'default';
		}
	}
}

