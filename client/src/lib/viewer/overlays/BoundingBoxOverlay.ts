import type { int } from '$lib/types';
import type { RenderTarget } from '$lib/webgl/types';
import type { Overlay } from '../viewer-utils';
import type { ViewerContext } from '../viewerContext.svelte';

type Box = [int, int, int, int]; // x1, y1, x2, y2

export class BoundingBoxOverlay implements Overlay {
	lineWidth = 3;
	strokeStyle = 'rgba(255,255,255,1)';
	hide = false;
	name: string = 'BoundingBox';
	annotationID: number = 0;

	boundingBoxes: Box[] = [];

	constructor() { }

	addBoundingBox(bb: Box) {
		this.boundingBoxes.push(bb);
	}

	repaint(viewerContext: ViewerContext, renderTarget: RenderTarget) {
		if (this.hide) return;
		if (!this.boundingBoxes) return;

		const { context2D, image } = viewerContext;
		context2D.lineWidth = this.lineWidth;
		context2D.strokeStyle = this.strokeStyle;

		if (!image.is3D) {
			for (var bb of this.boundingBoxes) {
				var p1 = viewerContext.imageToViewerCoordinates({ x: bb[0], y: bb[1] });
				var p2 = viewerContext.imageToViewerCoordinates({ x: bb[2], y: bb[3] });

				context2D.beginPath();
				context2D.moveTo(p1.x, p1.y);
				context2D.lineTo(p1.x, p2.y);
				context2D.lineTo(p2.x, p2.y);
				context2D.lineTo(p2.x, p1.y);
				context2D.lineTo(p1.x, p1.y);

				context2D.stroke();
			}
		}
	}
}
