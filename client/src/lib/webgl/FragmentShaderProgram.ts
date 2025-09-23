import type { ProgramInfo } from './programInfo';
import type { RenderTarget } from './types';
import type { WebGL } from './webgl';

export abstract class FragmentShaderProgram {
	constructor(
		protected readonly gl: WebGL2RenderingContext,
		protected readonly vertexArrayObject: WebGLVertexArrayObject,
		protected readonly programInfo: ProgramInfo
	) { }

	setUniforms(uniforms: { [name: string]: any }) {
		this.programInfo.setUniforms(uniforms);
	}

	abstract pass(renderTarget: RenderTarget, uniforms: { [name: string]: any }): void;
}

export class BaseTextureShaderProgram extends FragmentShaderProgram {

	constructor(webgl: WebGL, vertexShader: string, fragmentShader: string) {
		/*
		draw inside a rectangle with fragment coordinates v_uv 0-1
		specify these uniforms to determine the position of the rectangle:
		uniform mat3 u_transform;
		uniform vec2 u_image_size;
		uniform vec2 u_viewer_size;
		*/
		const gl = webgl.gl;
		const programInfo = webgl.createProgramInfo(vertexShader, fragmentShader);

		const positionAttributeLocation = gl.getAttribLocation(programInfo.program, 'a_position');
		const positionBuffer = gl.createBuffer();
		gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
		gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([
			0, 1,
			1, 0,
			0, 0,
			0, 1,
			1, 1,
			1, 0
		]), gl.STATIC_DRAW);

		const vertexArrayObject = gl.createVertexArray()!;

		gl.bindVertexArray(vertexArrayObject);
		gl.enableVertexAttribArray(positionAttributeLocation);
		gl.vertexAttribPointer(positionAttributeLocation, 2, gl.FLOAT, false, 0, 0);
		gl.enable(gl.SCISSOR_TEST);

		super(gl, vertexArrayObject, programInfo);
	}

	pass(renderTarget: RenderTarget, uniforms: { [name: string]: any }) {

		const gl = this.gl;
		const { left, bottom, width, height, framebuffer } = renderTarget;

		gl.bindFramebuffer(gl.FRAMEBUFFER, framebuffer);
		gl.viewport(left, bottom, width, height);
		gl.scissor(left, bottom, width, height);

		if (renderTarget.attachments) {
			gl.drawBuffers(renderTarget.attachments);
		}

		gl.enable(gl.BLEND);
		gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

		gl.useProgram(this.programInfo.program);
		gl.bindVertexArray(this.vertexArrayObject);		
		this.setUniforms(uniforms);
		gl.drawArrays(gl.TRIANGLES, 0, 6);
	}
}

export class TextureShaderProgram extends BaseTextureShaderProgram {
	constructor(webgl: WebGL, fragmentShader: string) {
		super(webgl, textureVertexShader, fragmentShader);
	}
}
export class TextureShaderProgram3D extends BaseTextureShaderProgram {
	constructor(webgl: WebGL, fragmentShader: string) {
		super(webgl, textureVertexShader3D, fragmentShader);
	}
}
export class PixelShaderProgram extends FragmentShaderProgram {


	constructor(webgl: WebGL, readonly fragmentShader: string) {
		/*
			runs for every pixel in the fragment
		*/

		const gl = webgl.gl;
		const programInfo = webgl.createProgramInfo(pixelVertexShader, fragmentShader);

		const positionAttributeLocation = gl.getAttribLocation(programInfo.program, 'a_position');
		const positionBuffer = gl.createBuffer();
		gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
		//triangle covering the whole screen
		gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, 3, 3, -1, -1, -1]), gl.STATIC_DRAW);

		const vertexArrayObject = gl.createVertexArray()!;

		gl.bindVertexArray(vertexArrayObject);
		gl.enableVertexAttribArray(positionAttributeLocation);
		gl.vertexAttribPointer(positionAttributeLocation, 2, gl.FLOAT, false, 0, 0);
		gl.enable(gl.SCISSOR_TEST);

		super(gl, vertexArrayObject, programInfo);
	}


	pass(renderTarget: RenderTarget, uniforms: { [name: string]: any }) {
		const gl = this.gl;
		const { left, bottom, width, height } = renderTarget;

		gl.bindFramebuffer(gl.FRAMEBUFFER, renderTarget.framebuffer);
		gl.viewport(left, bottom, width, height);
		gl.scissor(left, bottom, width, height);

		if (renderTarget.attachments) {
			gl.drawBuffers(renderTarget.attachments);
		}

		gl.useProgram(this.programInfo.program);
		gl.bindVertexArray(this.vertexArrayObject);
		this.setUniforms(uniforms);

		gl.drawArrays(gl.TRIANGLES, 0, 3);
	}
}

export class AffineShaderProgram extends FragmentShaderProgram {

	constructor(webgl: WebGL, fragmentShader: string) {

		const gl = webgl.gl;
		const programInfo = webgl.createProgramInfo(affineVertexShader, fragmentShader);

		const positionAttributeLocation = gl.getAttribLocation(programInfo.program, 'a_position');
		const positionBuffer = gl.createBuffer();
		gl.bindBuffer(gl.ARRAY_BUFFER, positionBuffer);
		gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([
			0, 1,
			1, 0,
			0, 0,
			0, 1,
			1, 1,
			1, 0
		]), gl.STATIC_DRAW);

		const vertexArrayObject = gl.createVertexArray()!;

		gl.bindVertexArray(vertexArrayObject);
		gl.enableVertexAttribArray(positionAttributeLocation);
		gl.vertexAttribPointer(positionAttributeLocation, 2, gl.FLOAT, false, 0, 0);
		gl.enable(gl.SCISSOR_TEST);

		super(gl, vertexArrayObject, programInfo);
	}

	pass(renderTarget: RenderTarget, uniforms: { [name: string]: any }) {

		const gl = this.gl;
		const { left, bottom, width, height } = renderTarget;

		gl.bindFramebuffer(gl.FRAMEBUFFER, renderTarget.framebuffer);
		gl.viewport(left, bottom, width, height);
		gl.scissor(left, bottom, width, height);

		if (renderTarget.attachments) {
			gl.drawBuffers(renderTarget.attachments);
		}

		gl.enable(gl.BLEND);
		gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

		gl.useProgram(this.programInfo.program);
		gl.bindVertexArray(this.vertexArrayObject);
		this.setUniforms(uniforms);
		gl.drawArrays(gl.TRIANGLES, 0, 6);
	}
}


const textureVertexShader = `#version 300 es

// a_position attribute are corners of the image (0,0) - (1,1)
// forwarded to fragment shader as v_uv
in vec4 a_position;
out vec2 v_uv;

// u_transform is a matrix that transforms image coordinates (0,0) - (w,h) to clip space (-1,-1) - (1,1)
uniform mat3 u_transform;
// size [w,h,d] of the image
uniform vec3 u_image_size;

void main() {
	vec3 p_in = vec3(u_image_size.xy * a_position.xy, 1.0);
    vec3 p = u_transform * p_in; 
	gl_Position = vec4(p, 1.0);	
	v_uv = a_position.xy;
}`;

const textureVertexShader3D = `#version 300 es
in vec4 a_position;
out vec3 v_uv;

uniform mat3 u_transform;
uniform mat3 u_image_transform;
uniform vec3 u_image_size;
uniform vec2 u_viewer_size;

uniform int u_index;
uniform vec2 u_translate;
uniform vec2 u_scale;

void main() {
	vec3 p_in = vec3(u_image_size.xy * a_position.xy, 1.0);
	vec3 p = u_transform * p_in;
	gl_Position = vec4(p, 1.0);
	v_uv = vec3(a_position.xy, (float(u_index) + 0.5) / u_image_size.z);
}`;


const pixelVertexShader = `#version 300 es
in vec4 a_position;
void main() {
    gl_Position = a_position;
}`;


const affineVertexShader = `#version 300 es
in vec4 a_position;
out vec2 v_uv;

uniform vec2 u_translate;
uniform vec2 u_scale;
uniform vec3 u_image_size;
uniform vec2 u_viewer_size;


void main() {
	// TODO: use matrix ?
    vec2 t = vec2(u_translate.x, -u_translate.y);
	vec2 p = a_position.xy; // [0-1]
	vec2 p1 = p * u_image_size.xy; // [0-w]
	vec2 p2 = p1 * u_scale + u_translate; 
    vec2 pos = 2.0 * p2 / u_viewer_size;
    gl_Position = vec4(pos.x - 1.0, 1.0 - pos.y, 0.0, 1.0);//a_position;
	v_uv = a_position.xy;
}`;
