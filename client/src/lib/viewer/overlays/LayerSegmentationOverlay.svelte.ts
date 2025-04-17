import type { Registration } from "$lib/registration/registration";
import type { SegmentationContext } from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
import { getBaseUniforms } from "$lib/webgl/imageRenderer";
import { LayerBitsSegmentation, type LabelNumbersSegmentation } from "$lib/webgl/layerSegmentation";
import type { Shaders } from "$lib/webgl/shaders";
import type { RenderTarget } from "$lib/webgl/types";
import type { Overlay } from "../viewer-utils";
import type { ViewerContext } from "../viewerContext.svelte";

export class LayerSegmentationOverlay implements Overlay {

	private colors: number[] = new Array(32 * 3).fill(0);
	alpha = $state(0.8);

	constructor(
		private readonly registration: Registration,
		private readonly segmentation: LabelNumbersSegmentation | LayerBitsSegmentation,
		public readonly segmentationContext: SegmentationContext,
		private shaders: Shaders

	) {
		// alternating even and odd colors from tab20
		// because neighboring pairs of colors are in tab20 are very similar
		for (let i = 0; i < 10; i++) {
			this.colors.splice(i * 3, 3, ...tab20[2 * i].map(c => c / 255));
		}
		for (let i = 0; i < 10; i++) {
			this.colors.splice((i + 10) * 3, 3, ...tab20[2 * i + 1].map(c => c / 255));
		}
	}

	repaint(viewerContext: ViewerContext, renderTarget: RenderTarget) {
		const {
			hideCreators,
			hideFeatures,
			hideSegmentations,
			hideAnnotations
		} = this.segmentationContext;


		if (hideSegmentations.has(this.segmentation)) return;
		const { annotation } = this.segmentation;
		if (hideAnnotations.has(annotation)) return;
		if (hideCreators.has(annotation.creator)) return;
		if (hideFeatures.has(annotation.feature)) return;

		const position = this.registration.getPosition(viewerContext.image.image_id);
		if (!position) return;

		const scanNr = viewerContext.index;
		const voxel = this.segmentation.data.getVoxel(Math.round(position.x), Math.round(position.y), scanNr);

		const baseUniforms = getBaseUniforms(viewerContext);
		const uniforms = {
			...baseUniforms,
			u_colors: this.colors,
			u_annotation: this.segmentation.data.getTexture(scanNr),
			u_alpha: this.alpha,
			u_highlight: voxel,
			u_questionable_bit: this.segmentation.questionable_bit,
		};

		if (this.segmentation instanceof LayerBitsSegmentation) {
			this.shaders.renderLayerBits.pass(renderTarget, uniforms);
		} else {
			if (this.segmentation.boundaries) {
				uniforms.u_boundaries = this.segmentation.boundaries.texture;
			}
			this.shaders.renderLabelNumbers.pass(renderTarget, uniforms);
		}

	}

}


const tab20 = [
	[31, 119, 180],
	[174, 199, 232],
	[255, 127, 14],
	[255, 187, 120],
	[44, 160, 44],
	[152, 223, 138],
	[214, 39, 40],
	[255, 152, 150],
	[148, 103, 189],
	[197, 176, 213],
	[140, 86, 75],
	[196, 156, 148],
	[227, 119, 194],
	[247, 182, 210],
	[127, 127, 127],
	[199, 199, 199],
	[188, 189, 34],
	[219, 219, 141],
	[23, 190, 207],
	[158, 218, 229],
]