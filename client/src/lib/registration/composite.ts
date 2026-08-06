import type { Position } from "$lib/types";
import type { RegistrationItem } from "./registrationItem";
import { composeGlslPath } from "./composeGlslPath";

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
        // CompositeRegistration still exposes a single mapping() for consumers
        // that expect RegistrationItem.glslMapping to be composable as one hop.
        // For multi-transform edges, bake the chain into one map_hop wrapper:
        if (hops.length === 0) return "";
        const inner = composeGlslPath(hops);
        // Re-wrap composed mapping() as map_hop for further composition:
        return inner.replace(
            /vec2\s+mapping\s*\(\s*vec2\s+uv\s*\)/,
            "vec2 map_hop(vec2 uv)",
        );
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
