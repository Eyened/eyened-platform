import type { Overlay } from '../viewer-utils';
import type { ViewerContext } from '../viewerContext.svelte';
import type { RenderTarget } from '$lib/webgl/types';

export class CursorOverlay implements Overlay {
	lineWidth = 1;
	strokeStyle = 'rgba(255,255,255,0.5)';
	opening = 10;

	name: string = 'Cursor';
	annotationID: number = 0;
	crosshairLen = 10000;

	constructor() { }

	repaint(viewerContext: ViewerContext, renderTarget: RenderTarget) {

		if (viewerContext.active) {
			return; // do not show if cursor is over this image
		}

		const { image, context2D, registration } = viewerContext;
		// const position = registration.pointer[image.image_id];
		const position = registration.getPosition(image.image_id);
		if (!position) return;

		context2D.lineWidth = this.lineWidth;
		context2D.strokeStyle = this.strokeStyle;

		if (image.is3D) {
			const p_top = viewerContext.imageToViewerCoordinates({ x: position.x, y: 0 });
			const p_bottom = viewerContext.imageToViewerCoordinates({
				x: position.x,
				y: image.height
			});
			const p_left = viewerContext.imageToViewerCoordinates({ x: 0, y: position.y });
			const p_right = viewerContext.imageToViewerCoordinates({ x: this.crosshairLen, y: position.y });

			context2D.beginPath();
			context2D.moveTo(p_top.x, p_top.y);
			context2D.lineTo(p_bottom.x, p_bottom.y);

			context2D.moveTo(p_left.x, p_left.y);
			context2D.lineTo(p_right.x, p_right.y);
			context2D.stroke();
		} else {
			const p = viewerContext.imageToViewerCoordinates(position);

			const r0 = this.crosshairLen;
			const r1 = this.opening;

			context2D.beginPath();
			context2D.moveTo(p.x - r0, p.y);
			context2D.lineTo(p.x - r1, p.y);

			context2D.moveTo(p.x + r0, p.y);
			context2D.lineTo(p.x + r1, p.y);

			context2D.moveTo(p.x, p.y - r0);
			context2D.lineTo(p.x, p.y - r1);

			context2D.moveTo(p.x, p.y + r0);
			context2D.lineTo(p.x, p.y + r1);

			context2D.stroke();
		}
	}
}
