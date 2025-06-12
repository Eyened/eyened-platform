import type { ETDRSCoordinates, Position2D } from '$lib/types';
import type { Overlay, ViewerEvent } from '../viewer-utils';
import type { RenderTarget } from '$lib/webgl/types';
import type { FormAnnotation } from '$lib/datamodel/formAnnotation';
import type { ViewerContext } from '../viewerContext.svelte';

const strokeStyleFovea = 'rgba(255, 255, 0, 1)';
const strokeStyleDisk = 'rgba(0, 255, 255, 1)';
const radius = 6;

export class ETDRSGridTool implements Overlay {

	toolName = 'ETRDS-grid';
	name: string = 'ETDRS-grid tool';
	annotation: FormAnnotation | undefined = $state();

	constructor(private readonly image_id: string) { }

	pointerdown(pointerEvent: ViewerEvent<PointerEvent>) {
		const { event, viewerContext, cursor } = pointerEvent;
		if (event.shiftKey) return;

		if (!this.annotation) return;

		const updateLandmark = async (name: 'fovea' | 'disc_edge') => {
			// const value = this.annotation!.value;
			// const data = await value.load() || {};
            const data = this.annotation!.value || {};
			data[name] = viewerContext.viewerToImageCoordinates(cursor);
			this.annotation!.update({ value: data });
		};
		if (event.button === 0) updateLandmark('fovea');
		if (event.button === 2) updateLandmark('disc_edge');
	}

	repaint(viewerContext: ViewerContext, renderTarget: RenderTarget) {
		if (!this.annotation) return;

		const coordinates: ETDRSCoordinates = this.annotation.value;
		if (!coordinates) return;
		const ctx = viewerContext.context2D;
		ctx.lineWidth = 1;
		ctx.fillStyle = 'white';

		this.paintMarker(coordinates.fovea, ctx, viewerContext, strokeStyleFovea);
		this.paintMarker(coordinates.disc_edge, ctx, viewerContext, strokeStyleDisk);
	}

	paintMarker(
		position: Position2D | undefined,
		ctx: CanvasRenderingContext2D,
		viewerContext: ViewerContext,
		strokeStyle: string
	) {
		if (!position) return;
		ctx.strokeStyle = strokeStyle;
		const p = viewerContext.imageToViewerCoordinates(position);
		ctx.strokeRect(p.x - radius, p.y - radius, 2 * radius, 2 * radius);
	}
}