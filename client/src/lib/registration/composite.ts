import type { Position } from "$lib/types";
import type { RegistrationItem } from "./registrationItem";

const MAP_HOP_DECL = /vec2\s+map_hop\s*\(\s*vec2\s+uv\s*\)/g;
const NUMBERED_MAP_DECL = /vec2\s+map_(\d+)\s*\(\s*vec2\s+uv\s*\)/g;

/**
 * CompositeRegistration is a class that represents a composite registration
 * between two images. It is used to apply a series of transformations
 *
 */
export class CompositeRegistration implements RegistrationItem {
    constructor(
        public readonly source: string,
        public readonly target: string,
        public readonly transforms: RegistrationItem[],
    ) {}

    mapping(p: Position): Position | undefined {
        let result: Position | undefined = p;
        for (const transform of this.transforms) {
            result = transform.mapping(result);
            if (!result) {
                return undefined;
            }
        }
        return result;
    }

    get glslMapping(): string {
        const hops = this.transforms
            .map((t) => t.glslMapping)
            .filter((s) => s.trim().length > 0);
        if (hops.length === 0) return "";

        const reserved = new Set(
            hops.flatMap((hop) =>
                [...hop.matchAll(NUMBERED_MAP_DECL)].map((match) =>
                    Number(match[1]),
                ),
            ),
        );
        const helperNames: string[] = [];
        let nextIndex = 0;
        const helpers = hops.map((hop) => {
            while (reserved.has(nextIndex)) nextIndex++;
            const helperName = `map_${nextIndex}`;
            reserved.add(nextIndex);
            nextIndex++;
            helperNames.push(helperName);
            return hop.replace(MAP_HOP_DECL, `vec2 ${helperName}(vec2 uv)`);
        });
        let wrapper = "vec2 map_hop(vec2 uv) {\n";
        for (const helperName of helperNames) {
            wrapper += `  uv = ${helperName}(uv);\n`;
        }
        wrapper += "  return uv;\n}";

        return `${helpers.join("\n")}\n${wrapper}`;
    }

    get inverse(): CompositeRegistration {
        const inverseTransforms = this.transforms
            .map((t) => t.inverse)
            .reverse();
        return new CompositeRegistration(
            this.target,
            this.source,
            inverseTransforms,
        );
    }
}
