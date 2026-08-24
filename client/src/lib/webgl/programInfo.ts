type UniformSetter = (v: any) => void;

export class ProgramInfo {
	program: WebGLProgram;
	uniformSetters: { [name: string]: UniformSetter } = {};
	textureUnits: { [name: string]: number } = {};
	uniformLocations: { [name: string]: WebGLUniformLocation } = {};

	private colorAttachments: number[];
	private samplerToTexture: { [sampler: number]: number };
	private typeToUniformMatrixSetter: { [type: number]: any };
	private typeToUniformSetter: { [type: number]: any };
	private typeToUniformArraySetter: { [type: number]: any };
	private samplerTypes: Set<number>;
	typeToUniformVecSetter: { [x: number]: (location: WebGLUniformLocation | null, x: number, y: number, z: number, w: number) => void; };

	constructor(private readonly gl: WebGL2RenderingContext, vertexShader: WebGLShader, fragmentShader: WebGLShader) {

		const program = gl.createProgram()!;

		gl.attachShader(program, vertexShader);
		gl.attachShader(program, fragmentShader);
		gl.linkProgram(program);

		this.program = program;

		this.colorAttachments = [
			gl.COLOR_ATTACHMENT0,
			gl.COLOR_ATTACHMENT1,
			gl.COLOR_ATTACHMENT2,
			gl.COLOR_ATTACHMENT3,
			gl.COLOR_ATTACHMENT4,
			gl.COLOR_ATTACHMENT5,
			gl.COLOR_ATTACHMENT6,
			gl.COLOR_ATTACHMENT7
		];

		this.samplerToTexture = {
			[gl.SAMPLER_2D]: gl.TEXTURE_2D,
			[gl.INT_SAMPLER_2D]: gl.TEXTURE_2D,
			[gl.UNSIGNED_INT_SAMPLER_2D]: gl.TEXTURE_2D,
			[gl.SAMPLER_3D]: gl.TEXTURE_3D,
			[gl.INT_SAMPLER_3D]: gl.TEXTURE_3D,
			[gl.UNSIGNED_INT_SAMPLER_3D]: gl.TEXTURE_3D
		};

		this.samplerTypes = new Set([
			gl.SAMPLER_2D, gl.INT_SAMPLER_2D, gl.UNSIGNED_INT_SAMPLER_2D,
			gl.SAMPLER_3D, gl.INT_SAMPLER_3D, gl.UNSIGNED_INT_SAMPLER_3D, gl.SAMPLER_CUBE]);


		this.typeToUniformMatrixSetter = {
			[gl.FLOAT_MAT2]: gl.uniformMatrix2fv.bind(gl),
			[gl.FLOAT_MAT3]: gl.uniformMatrix3fv.bind(gl),
			[gl.FLOAT_MAT4]: gl.uniformMatrix4fv.bind(gl)
		};

		this.typeToUniformSetter = {
			[gl.FLOAT]: gl.uniform1f.bind(gl),
			[gl.INT]: gl.uniform1i.bind(gl),
			[gl.UNSIGNED_INT]: gl.uniform1ui.bind(gl),
			[gl.BOOL]: gl.uniform1i.bind(gl),
		};

		this.typeToUniformVecSetter = {
			[gl.FLOAT_VEC2]: gl.uniform2f.bind(gl),
			[gl.FLOAT_VEC3]: gl.uniform3f.bind(gl),
			[gl.FLOAT_VEC4]: gl.uniform4f.bind(gl),

			[gl.INT_VEC2]: gl.uniform2i.bind(gl),
			[gl.INT_VEC3]: gl.uniform3i.bind(gl),
			[gl.INT_VEC4]: gl.uniform4i.bind(gl),

			[gl.UNSIGNED_INT_VEC2]: gl.uniform2ui.bind(gl),
			[gl.UNSIGNED_INT_VEC3]: gl.uniform3ui.bind(gl),
			[gl.UNSIGNED_INT_VEC4]: gl.uniform4ui.bind(gl),

			[gl.BOOL_VEC2]: gl.uniform2i.bind(gl),
			[gl.BOOL_VEC3]: gl.uniform3i.bind(gl),
			[gl.BOOL_VEC4]: gl.uniform4i.bind(gl)
		};

		this.typeToUniformArraySetter = {
			[gl.FLOAT]: gl.uniform1fv.bind(gl),
			[gl.FLOAT_VEC2]: gl.uniform2fv.bind(gl),
			[gl.FLOAT_VEC3]: gl.uniform3fv.bind(gl),
			[gl.FLOAT_VEC4]: gl.uniform4fv.bind(gl),
			[gl.INT]: gl.uniform1iv.bind(gl),
			[gl.INT_VEC2]: gl.uniform2iv.bind(gl),
			[gl.INT_VEC3]: gl.uniform3iv.bind(gl),
			[gl.INT_VEC4]: gl.uniform4iv.bind(gl),
			[gl.UNSIGNED_INT]: gl.uniform1uiv.bind(gl),
			[gl.UNSIGNED_INT_VEC2]: gl.uniform2uiv.bind(gl),
			[gl.UNSIGNED_INT_VEC3]: gl.uniform3uiv.bind(gl),
			[gl.UNSIGNED_INT_VEC4]: gl.uniform4uiv.bind(gl),
			[gl.BOOL]: gl.uniform1iv.bind(gl),
			[gl.BOOL_VEC2]: gl.uniform2iv.bind(gl),
			[gl.BOOL_VEC3]: gl.uniform3iv.bind(gl),
			[gl.BOOL_VEC4]: gl.uniform4iv.bind(gl)
		};

		this.init();
	}

	private init() {
		const gl = this.gl;
		const numUniforms = gl.getProgramParameter(this.program, gl.ACTIVE_UNIFORMS);

		for (let i = 0; i < numUniforms; ++i) {
			const info = gl.getActiveUniform(this.program, i)!;

			let name = info.name;
			// Remove the array indices if found
			const bracketIndex = name.indexOf('[');
			if (bracketIndex !== -1) {
				name = name.substring(0, bracketIndex);
			}
			const location = gl.getUniformLocation(this.program, name)!;

			this.uniformSetters[name] = this.getSetter(info, location);
		}
	}

	setUniform(name: string, value: any) {
		if (!this.uniformSetters.hasOwnProperty(name)) {
			return;
		}
		this.uniformSetters[name](value);
	}

	getSetter(info: WebGLActiveInfo, location: WebGLUniformLocation): UniformSetter {
		if (this.samplerTypes.has(info.type)) {
			return this.getSamplerSetter(info, location);
		} else if (info.type in this.typeToUniformMatrixSetter) {
			// matrix
			const uniformFunction = this.typeToUniformMatrixSetter[info.type];
			return (v: any) => uniformFunction(location, false, v);
		} else if (info.size > 1) {
			// array 
			const uniformFunction = this.typeToUniformArraySetter[info.type];
			return (v: any) => uniformFunction(location, v);
		} else if (info.type in this.typeToUniformVecSetter) {
			// vector
			const uniformFunction = this.typeToUniformVecSetter[info.type];
			return (v: any) => uniformFunction(location, ...v);
		} else {
			// other
			const uniformFunction = this.typeToUniformSetter[info.type];
			return (v: any) => uniformFunction(location, v);
		}

	}

	private currentTextureUnit: number = 0;
	getSamplerSetter(info: WebGLActiveInfo, location: WebGLUniformLocation): UniformSetter {
		const gl = this.gl;
		const textureUnit = this.currentTextureUnit;  // Store the current unit for this sampler

		// Increment the unit for the next texture
		this.currentTextureUnit++;
		return (v: WebGLTexture) => {
			gl.activeTexture(gl.TEXTURE0 + textureUnit);
			gl.bindTexture(this.samplerToTexture[info.type], v);
			gl.uniform1i(location, textureUnit);
		};
	}

	setUniforms(uniforms: { [name: string]: any }) {
		for (const [name, value] of Object.entries(uniforms)) {
			this.setUniform(name, value);
		}
		for (const name in this.uniformSetters) {
			if (!(name in uniforms)) {
				throw new Error(`Missing uniform ${name}`);
			}
		}
	}
}