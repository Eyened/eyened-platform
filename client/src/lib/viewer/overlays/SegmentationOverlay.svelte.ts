import type { Color } from "$lib/utils";
import type { SegmentationContext } from "$lib/viewer-window/panelSegmentation/segmentationContext.svelte";
import type { TextureShaderProgram } from "$lib/webgl/FragmentShaderProgram";
import type { Segmentation, SegmentationController } from "$lib/webgl/SegmentationController";
import { MaskedSegmentation } from "$lib/webgl/binarySegmentation";
import { getBaseUniforms } from "$lib/webgl/imageRenderer";
import type { RenderTarget } from "$lib/webgl/types";
import type { Overlay } from "../viewer-utils";
import type { ViewerContext } from "../viewerContext.svelte";
import { colors } from "./colors";
import { ConnectedComponentsOverlay } from "./ConnectedComponentsOverlay";
import { ProbabilitySegmentation } from "$lib/webgl/probabilitySegmentation.svelte";
import { SvelteMap, SvelteSet } from "svelte/reactivity";

export class SegmentationOverlay implements Overlay {

	private featureColors = new SvelteMap<Segmentation, Color>();

	private readonly renderFeatures: TextureShaderProgram;
	private readonly renderProbability: TextureShaderProgram;
	public readonly connectedComponentsOverlay: ConnectedComponentsOverlay;

	public readonly applyMasking = new SvelteSet<Segmentation>();
	public readonly renderOutline = $state(false);
	public readonly alpha = $state(0.8);

	constructor(
		private readonly viewerContext: ViewerContext,
		private readonly segmentationController: SegmentationController,
		public readonly segmentationContext: SegmentationContext,
	) {
		const shaders = viewerContext.shaders;
		this.renderFeatures = shaders.renderFeatures;
		this.renderProbability = shaders.renderProbability;
		this.connectedComponentsOverlay = new ConnectedComponentsOverlay(viewerContext, segmentationContext);
	}

	toggleMasking(segmentation: Segmentation) {
		if (this.applyMasking.has(segmentation)) {
			this.applyMasking.delete(segmentation);
		} else {
			this.applyMasking.add(segmentation);
		}
	}

	setFeatureColor(segmentation: Segmentation, color: Color) {
		this.featureColors.set(segmentation, color);
	}

	private _colorIndex = 0;
	getFeatureColor(segmentation: Segmentation): Color {
		let color = this.featureColors.get(segmentation);
		if (!color) {
			color = colors[(this._colorIndex++) % colors.length];
			this.featureColors.set(segmentation, color);
		}
		return color;
	}

	repaint(viewerContext: ViewerContext, renderTarget: RenderTarget) {
		const { hideOverlays } = viewerContext;
		if (hideOverlays) {
			return;
		}

		this.paintBinarySegmentations(viewerContext, renderTarget);
		this.paintProbability(viewerContext, renderTarget);
		this.connectedComponentsOverlay.paint(viewerContext, renderTarget);
	}


	paintBinarySegmentations(viewerContext: ViewerContext, renderTarget: RenderTarget) {

		const { image: { segmentationController }, index } = viewerContext;
		const {
			hideCreators,
			hideFeatures,
			hideSegmentations,
			hideAnnotations
		} = this.segmentationContext;

		const baseUniforms = getBaseUniforms(viewerContext);
		const uniforms = {
			...baseUniforms,
			u_alpha: this.alpha,
			u_smooth: true
		};

		// each sharedData holds a set of segmentations		
		for (const [data, segmentations] of segmentationController.sharedData.entries()) {

			for (const segmentation of segmentations) {
				if (!segmentation) continue;
				const { annotation } = segmentation;

				if (hideAnnotations.has(annotation)) continue;
				if (hideSegmentations.has(segmentation)) continue;
				if (hideCreators.has(annotation.creator)) continue;
				if (hideFeatures.has(annotation.feature)) continue;

				if (this.connectedComponentsOverlay.mode.has(segmentation)) continue;

				uniforms.u_annotation = data.getTexture(index);
				uniforms.u_layer_bit = segmentation.layerBit;
				uniforms.u_color = this.getFeatureColor(segmentation).map(c => c / 255);
				uniforms.u_outline = this.renderOutline;
				if (segmentation instanceof MaskedSegmentation && this.applyMasking.has(segmentation)) {
					uniforms.u_mask = segmentation.maskSegmentation.data.getTexture(index);
					uniforms.u_mask_bit = segmentation.maskSegmentation.layerBit;
				} else {
					// need to set the texture to something, otherwise the shader might not work
					uniforms.u_mask = uniforms.u_annotation;
					uniforms.u_mask_bit = 0;
				}
				this.renderFeatures.pass(renderTarget, uniforms);
			}
		}
	}


	paintProbability(viewerContext: ViewerContext, renderTarget: RenderTarget) {

		const { index } = viewerContext;
		const {
			hideCreators,
			hideFeatures,
			hideSegmentations,
			hideAnnotations
		} = this.segmentationContext;

		const baseUniforms = getBaseUniforms(viewerContext);
		const uniforms = {
			...baseUniforms
		};
		for (const segmentation of this.segmentationController.allSegmentations) {
			const { annotation } = segmentation;
			if (hideAnnotations.has(annotation)) continue;


			if (hideSegmentations.has(segmentation)) continue;
			if (hideCreators.has(annotation.creator)) continue;
			if (hideFeatures.has(annotation.feature)) continue;
			if (segmentation instanceof ProbabilitySegmentation) {
				uniforms.u_annotation = segmentation.getTexture(index);
				uniforms.u_threshold = segmentation.threshold;
				uniforms.u_color = this.getFeatureColor(segmentation).map(c => c / 255);
				this.renderProbability.pass(renderTarget, uniforms);
			}
		}
	}

}
