import type { Position } from "$lib/types";
import type { RegistrationItem } from "./registrationItem";
/**
 * CompositeRegistration is a class that represents a composite registration
 * between two images. It is used to apply a series of transformations
 * 
 */
export class CompositeRegistration implements RegistrationItem {

    constructor(
        public readonly source: string,
        public readonly target: string,
        public readonly transforms: RegistrationItem[]) { }

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
        let result = '';
        let i = 0;
        for (const transform of this.transforms) {
            const subMapping = transform.glslMapping;
            subMapping.replace(`vec2 mapping`, `vec2 mapping_${i}`);  
            result += subMapping;
            i++;
        }
        result += `vec2 mapping(vec2 uv) {`;
        for (let j = 0; j < i; j++) {
            result += `uv = mapping_${j}(uv);`;
        }
        result += `return uv;}`;
        return result;
    }

    get inverse(): CompositeRegistration {
        const inverseTransforms = this.transforms.map(t => t.inverse).reverse();
        return new CompositeRegistration(this.target, this.source, inverseTransforms);
    }
}