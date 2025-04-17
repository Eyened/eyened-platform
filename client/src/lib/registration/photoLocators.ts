import type { Position } from "$lib/types";
import { vec2 } from "$lib/vec2";
import type { ViewerContext } from "$lib/viewer/viewerContext.svelte";
import type { AbstractImage } from "$lib/webgl/abstractImage";
import { getDicomRegistration } from "./dicomRegistration";
import { getFdsRegistration } from "./fdsRegistration";
import { getPrivateEyeRegistrationHeidelberg } from "./privateEyeRegistrationHeidelberg";
import type { RegistrationItem } from "./registrationItem";

type Point = { x: number, y: number };

export class OCTToEnfacePhotolocations implements RegistrationItem {

    _photoLocators: PhotoLocator[] = [];
    glslMapping: string = ""; // meant for 2D mapping in same plane

    constructor(
        public readonly source: string,
        public readonly target: string,
        public readonly photoLocators: PhotoLocator[]
    ) {
        for (const locator of this.photoLocators) {
            if (this._photoLocators.length <= locator.index) {
                this._photoLocators.length = locator.index + 1;
            }
            this._photoLocators[locator.index] = locator;
        }
    }

    mapping(p: Position): Position | undefined {
        return this._photoLocators[p.index]?.OCTToEnface(p);
    }

    get inverse(): RegistrationItem {
        return new EnfaceToOCTPhotolocations(this.target, this.source, this.photoLocators);
    }
}

export class EnfaceToOCTPhotolocations implements RegistrationItem {

    glslMapping: string = ""; // meant for 2D mapping in same plane

    constructor(
        public readonly source: string,
        public readonly target: string,
        public readonly photoLocators: PhotoLocator[]
    ) { }

    mapping(p: Position): Position | undefined {
        let minDistance = Infinity;
        let closestPosition: Position | undefined;

        for (const locator of this.photoLocators) {

            const { distance, position } = locator.enfaceToOCT(p);
            if (distance < minDistance) {
                minDistance = distance;
                closestPosition = position;
            }
        }
        return closestPosition;
    }

    get inverse(): RegistrationItem {
        return new OCTToEnfacePhotolocations(this.target, this.source, this.photoLocators);
    }
}

export interface PhotoLocator {
    readonly enfaceImageId: string;
    readonly octImageId: string;
    readonly index: number;
    enfaceToOCT(p: Position): { position: Position, distance: number };
    OCTToEnface(p: Position): Position;
    paint(ctx: CanvasRenderingContext2D, viewerContext: ViewerContext): void;
}

export class LinePhotoLocator implements PhotoLocator {

    public readonly length: number;

    constructor(
        public readonly enfaceImageId: string,
        public readonly octImageId: string,
        public readonly start: Point,
        public readonly end: Point,
        public readonly index: number,
        public readonly width: number
    ) {
        this.length = Math.sqrt((end.x - start.x) ** 2 + (end.y - start.y) ** 2);
    }

    OCTToEnface(p: Position): Position {
        const { start, end } = this;
        const r = p.x / this.width;
        return {
            x: start.x + r * (end.x - start.x),
            y: start.y + r * (end.y - start.y),
            index: 0
        };
    }

    enfaceToOCT(p: Position): { position: Position, distance: number } {

        const s = vec2(this.start);
        const e = vec2(this.end);
        const lineVec = e.sub(s);
        // length of the line on the enface
        const l = lineVec.length();

        // vector from start to cursor        
        const ptVec = vec2(p).sub(s);
        // project cursor on the line
        // dist is the distance from the start of the line to the projected point
        const parallel = ptVec.dot(lineVec) / l;

        // perpendicular distance to line
        const distance = Math.abs(lineVec.cross(ptVec)) / l;

        const position = {
            index: this.index,
            x: this.width * parallel / l,
            y: 0
        };
        return { position, distance };
    }

    paint(ctx: CanvasRenderingContext2D, viewerContext: ViewerContext): void {
        const s = viewerContext.imageToViewerCoordinates(this.start);
        const e = viewerContext.imageToViewerCoordinates(this.end);

        ctx.beginPath();
        ctx.moveTo(s.x, s.y);
        ctx.lineTo(e.x, e.y);
        ctx.stroke();


    }
}

export class CirclePhotoLocator implements PhotoLocator {
    constructor(
        public readonly enfaceImageId: string,
        public readonly octImageId: string,
        public readonly centre: Point,
        public readonly radius: number,
        public readonly start_angle: number,
        public readonly index: number,
        public readonly width: number
    ) { }

    OCTToEnface(p: Position): Position {
        const r = p.x / this.width;
        const { centre, radius, start_angle } = this;
        const angle = start_angle + 2 * r * Math.PI;
        const x = centre.x + radius * Math.cos(angle);
        const y = centre.y + radius * Math.sin(angle);
        return { x, y, index: 0 };
    }

    enfaceToOCT(p: Position): { position: Position, distance: number } {
        const { centre, radius, start_angle } = this;
        const vec = vec2(p).sub(centre);
        const distance = Math.abs(vec.length() - radius);
        const angle = vec.angle() - start_angle;
        const r = angle / (2 * Math.PI);
        const position = {
            index: this.index,
            x: this.width * r,
            y: 0
        };
        return { position, distance };

    }

    paint(ctx: CanvasRenderingContext2D, viewerContext: ViewerContext): void {
        const { centre, radius } = this;
        const c = viewerContext.imageToViewerCoordinates(centre);

        const crx = viewerContext.imageToViewerCoordinates({ x: centre.x + radius, y: centre.y });
        const cry = viewerContext.imageToViewerCoordinates({ x: centre.x, y: centre.y + radius });
        const radiusX = crx.x - c.x;
        const radiusY = cry.y - c.y;
        const { x, y } = c;
        ctx.beginPath();
        ctx.ellipse(x, y, radiusX, radiusY, 0, 0, 2 * Math.PI)
        ctx.stroke();
    }
}

export function loadPhotoLocators(image: AbstractImage) {
    const functions = [
        getDicomRegistration,
        getPrivateEyeRegistrationHeidelberg,
        getFdsRegistration
    ];
    return functions.flatMap(func => func(image));
}


export function photoLocatorsToRegistrationItems(photoLocators: PhotoLocator[]): RegistrationItem[] {
    // normally a list of photoLocators should link one enface image to one OCT image
    // However, theoretically a list of photoLocators can link multiple enface images to multiple OCT images
    // In this case, we create a registration item for each pair of enface and OCT images
    const enface_image_ids = new Set(photoLocators.map(loc => loc.enfaceImageId));
    const oct_image_ids = new Set(photoLocators.map(loc => loc.octImageId));
    const result: RegistrationItem[] = [];
    for (const enfaceID of enface_image_ids) {
        for (const octID of oct_image_ids) {
            const locators = photoLocators.filter(loc => loc.enfaceImageId === enfaceID && loc.octImageId === octID);
            if (locators.length > 0) {
                result.push(new OCTToEnfacePhotolocations(octID, enfaceID, locators));
                result.push(new EnfaceToOCTPhotolocations(enfaceID, octID, locators));
            }
        }
    }
    return result;
}