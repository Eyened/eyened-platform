import type { Position } from "$lib/types";
import type { ImageGET } from "../../types/openapi_types";
import type { RegistrationItem } from "./registrationItem";

export class OCTToProj implements RegistrationItem {
    public readonly source: string;
    public readonly target: string;
    constructor(public readonly instance: ImageGET) {
        this.source = `${instance.id}`;
        this.target = `${instance.id}_proj`;
    }

    mapping(p: Position): Position {
        return { x: p.x, y: p.index + 0.5, index: 0 };

    }

    get glslMapping(): string {
        // meant for 2D images in same plane
        return ``;
    }

    get inverse(): RegistrationItem {
        return new ProjToOCT(this.instance);
    }

}
export class ProjToOCT implements RegistrationItem {
    public readonly source: string;
    public readonly target: string;
    constructor(public readonly instance: ImageGET) {
        this.source = `${instance.id}_proj`;
        this.target = `${instance.id}`;
    }

    mapping(p: Position): Position {
        return {
            x: p.x,
            y: 0,
            index: Math.round(Math.max(0, Math.min(p.y, this.instance.nr_of_frames - 1)))
        }
    }

    get glslMapping(): string {
        // meant for 2D images in same plane
        return ``;
    }

    get inverse(): RegistrationItem {   
        return new OCTToProj(this.instance);
    }
}