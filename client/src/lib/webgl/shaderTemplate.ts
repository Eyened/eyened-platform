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
    /** `null` marks a key that already failed to compile, so we never retry it. */
    private readonly cache = new Map<string, TextureShaderProgram | null>();

    getOrCompile(
        webgl: WebGL,
        template: string,
        inserts: Record<string, string>,
    ): TextureShaderProgram | null {
        const key = shaderCacheKey(template, inserts);
        if (this.cache.has(key)) {
            return this.cache.get(key)!;
        }

        try {
            const source = applyInserts(template, inserts);
            const program = new TextureShaderProgram(webgl, source);
            this.cache.set(key, program);
            return program;
        } catch (err) {
            this.cache.set(key, null);
            console.error("ShaderTemplateCache: compile failed", err);
            throw err;
        }
    }
}

const cachesByWebGL = new WeakMap<WebGL, ShaderTemplateCache>();

/**
 * Shader programs are tied to a GL context, not to whoever asked for them.
 * Keying the cache on the `WebGL` instance lets short-lived consumers (overlays
 * that get recreated whenever their props change) reuse compiled programs.
 */
export function getShaderTemplateCache(webgl: WebGL): ShaderTemplateCache {
    let cache = cachesByWebGL.get(webgl);
    if (!cache) {
        cache = new ShaderTemplateCache();
        cachesByWebGL.set(webgl, cache);
    }
    return cache;
}
