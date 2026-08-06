import { TextureShaderProgram } from "./FragmentShaderProgram";
import type { WebGL } from "./webgl";

export function applyInserts(
    template: string,
    inserts: Record<string, string>,
): string {
    let out = template;
    for (const [name, code] of Object.entries(inserts)) {
        const marker = `// @insert ${name}`;
        if (!out.includes(marker)) {
            throw new Error(
                `applyInserts: template missing slot "// @insert ${name}"`,
            );
        }
        out = out.split(marker).join(code);
    }
    return out;
}

/** Deterministic cache key (not cryptographic). */
export function shaderCacheKey(
    template: string,
    inserts: Record<string, string>,
): string {
    const parts = Object.keys(inserts)
        .sort()
        .map((k) => `${k}=${inserts[k]}`);
    return `${template.length}:${fnv1a(template)}|${fnv1a(parts.join("\n"))}`;
}

function fnv1a(s: string): string {
    let h = 0x811c9dc5;
    for (let i = 0; i < s.length; i++) {
        h ^= s.charCodeAt(i);
        h = Math.imul(h, 0x01000193);
    }
    return (h >>> 0).toString(16);
}

export class ShaderTemplateCache {
    private readonly cache = new Map<string, TextureShaderProgram>();

    getOrCompile(
        webgl: WebGL,
        template: string,
        inserts: Record<string, string>,
    ): TextureShaderProgram {
        const key = shaderCacheKey(template, inserts);
        const hit = this.cache.get(key);
        if (hit) return hit;

        try {
            const source = applyInserts(template, inserts);
            const program = new TextureShaderProgram(webgl, source);
            this.cache.set(key, program);
            return program;
        } catch (err) {
            console.error("ShaderTemplateCache: compile failed", err);
            throw err;
        }
    }
}
