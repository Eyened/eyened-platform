import { TextureShaderProgram } from "./FragmentShaderProgram";
import type { WebGL } from "./webgl";

export function applyInserts(
    template: string,
    inserts: Record<string, string>,
): string {
    let out = template;
    for (const [name, code] of Object.entries(inserts)) {
        // vite-plugin-glsl strips ordinary `//` comments; `///` is preserved.
        // Check the triple-slash form first — `// @insert X` is a substring of
        // `/// @insert X`, so matching single-slash first would leave a stray `/`.
        const triple = `/// @insert ${name}`;
        const single = `// @insert ${name}`;
        const marker = out.includes(triple)
            ? triple
            : out.includes(single)
              ? single
              : null;
        if (!marker) {
            throw new Error(
                `applyInserts: template missing slot "// @insert ${name}" or "/// @insert ${name}"`,
            );
        }
        out = out.split(marker).join(code);
    }
    return out;
}

/** Compile a fragment template with insert slots. Caller owns/reuses the program. */
export function compileShaderTemplate(
    webgl: WebGL,
    template: string,
    inserts: Record<string, string>,
): TextureShaderProgram {
    return new TextureShaderProgram(webgl, applyInserts(template, inserts));
}
