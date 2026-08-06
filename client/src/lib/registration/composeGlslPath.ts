const MAP_HOP_DECL = /vec2\s+map_hop\s*\(\s*vec2\s+uv\s*\)/g;

/**
 * Compose single-hop GLSL snippets into one mapping(uv) function.
 * Each hop must declare `vec2 map_hop(vec2 uv)`.
 */
export function composeGlslPath(hops: string[]): string {
    const renamed: string[] = [];
    let count = 0;

    for (const hop of hops) {
        if (!hop.trim()) continue;
        if (!/\bmap_hop\b/.test(hop)) {
            throw new Error(
                "composeGlslPath: hop must define vec2 map_hop(vec2 uv)",
            );
        }
        renamed.push(
            hop.replace(MAP_HOP_DECL, `vec2 map_${count}(vec2 uv)`),
        );
        count++;
    }

    if (count === 0) {
        return `vec2 mapping(vec2 uv) { return uv; }`;
    }

    let mapping = `vec2 mapping(vec2 uv) {\n`;
    for (let i = 0; i < count; i++) {
        mapping += `  uv = map_${i}(uv);\n`;
    }
    mapping += `  return uv;\n}`;

    return `${renamed.join("\n")}\n${mapping}`;
}
