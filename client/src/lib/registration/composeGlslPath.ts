const MAP_HOP_DECL = /vec2\s+map_hop\s*\(\s*vec2\s+uv\s*\)/g;
const NUMBERED_MAP_DECL = /vec2\s+map_(\d+)\s*\(\s*vec2\s+uv\s*\)/g;

/**
 * Compose single-hop GLSL snippets into one mapping(uv) function.
 * Each hop must declare `vec2 map_hop(vec2 uv)`.
 */
export function composeGlslPath(hops: string[]): string {
    const nonEmptyHops = hops.filter((hop) => hop.trim());
    const reserved = new Set(
        nonEmptyHops.flatMap((hop) =>
            [...hop.matchAll(NUMBERED_MAP_DECL)].map((match) =>
                Number(match[1]),
            ),
        ),
    );
    const renamed: string[] = [];
    const helperNames: string[] = [];
    let nextIndex = 0;

    for (const hop of nonEmptyHops) {
        if (!/\bmap_hop\b/.test(hop)) {
            throw new Error(
                "composeGlslPath: hop must define vec2 map_hop(vec2 uv)",
            );
        }
        while (reserved.has(nextIndex)) nextIndex++;
        const helperName = `map_${nextIndex}`;
        reserved.add(nextIndex);
        nextIndex++;
        renamed.push(hop.replace(MAP_HOP_DECL, `vec2 ${helperName}(vec2 uv)`));
        helperNames.push(helperName);
    }

    if (helperNames.length === 0) {
        return `vec2 mapping(vec2 uv) { return uv; }`;
    }

    let mapping = `vec2 mapping(vec2 uv) {\n`;
    for (const helperName of helperNames) {
        mapping += `  uv = ${helperName}(uv);\n`;
    }
    mapping += `  return uv;\n}`;

    return `${renamed.join("\n")}\n${mapping}`;
}
