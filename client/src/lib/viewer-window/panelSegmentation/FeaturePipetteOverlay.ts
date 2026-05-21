import type { MainViewerContext } from '$lib/viewer/overlays/MainViewerContext.svelte';
import type { Overlay, ViewerEvent } from '$lib/viewer/viewer-utils';
import type { ViewerContext } from '$lib/viewer/viewerContext.svelte';
import type { RenderTarget } from '$lib/webgl/types';
import { handleFeaturePipetteKeydown } from './featurePipette';

/** Event-only overlay: A picks feature class or binary/questionable segmentation under cursor. */
export class FeaturePipetteOverlay implements Overlay {
	constructor(
		private readonly mainViewerContext: MainViewerContext,
		private readonly userId: number,
	) {}

	repaint(_viewerContext: ViewerContext, _renderTarget: RenderTarget): void {}

	keydown(e: ViewerEvent<KeyboardEvent>): void {
		handleFeaturePipetteKeydown(e, this.mainViewerContext, this.userId);
	}
}
