import type { Item } from "./itemList";
import { type MappingType } from "./mapping";
import type { DataModel } from "./model";


class AuxiliaryProperty {
    constructor(public readonly properties: string[]) { }

    define(item: any, key: string) {
        const properties = this.properties;
        Object.defineProperty(item, key, {
            enumerable: true,
            get: function () {
                let value = this;
                for (const prop of properties) {
                    if (value) {
                        value = value[prop];
                    } else {
                        return null;
                    }
                }
                return value;
            }
        });
    }
}

export function PropertyChain(properties: string[]) {
    return new AuxiliaryProperty(properties);
}

export class DerivedProperty {
    constructor(public readonly value: (self: any, data: DataModel) => any) { }

    define(item: any, key: string, data: DataModel) {
        const value = this.value;
        Object.defineProperty(item, key, {
            get: function () {
                return value(item, data);
            }
        });
    }
}



export class ItemConstructor<T extends Item> {
    constructor(
        public idMapping: number | string | ((params: any) => string | number),
        public readonly properties: { [key: string]: MappingType | AuxiliaryProperty | DerivedProperty }) {
    }

    getID(params: any): string | number {
        if (typeof this.idMapping === 'function') {
            return this.idMapping(params);
        } else {
            return params[this.idMapping];
        }
    }

    create(params: any): { id: string | number } {
        return { id: this.getID(params) };
    }

    toItem(item: any, params: any, data: DataModel, newData: any): T {
        for (const [key, mapping] of Object.entries(this.properties)) {
            if (mapping instanceof AuxiliaryProperty) {
                mapping.define(item, key);
            } else if (mapping instanceof DerivedProperty) {
                mapping.define(item, key, data);
            }
            else {
                item[key] = toValue(mapping, params, data, newData);
            }
        }
        // ensure that the object is immutable
        Object.freeze(item);
        return item as T;
    }

    toParams(item: Omit<T, 'id'>) {
        const result: any = {};
        for (const [key, mapping] of Object.entries(this.properties)) {
            if (item[key] === undefined) {
                // ignore, property might be optional
                continue;
            }
            if (typeof mapping === 'string') {
                result[mapping] = item[key];
            } else if (mapping instanceof AuxiliaryProperty) {
                // ignore
            } else if (mapping instanceof DerivedProperty) {
                // ignore
            } else {
                mapping.toParam(result, item[key]);
            }
        }
        return result;
    }
}

function toValue(mapping: MappingType, params: any, data: DataModel, newData: any): any {
    if (typeof mapping === 'string') {
        return params[mapping];
    }
    try {
        return mapping.toValue(params, data, newData);
    } catch (e) {
        console.error('toValue', mapping, params, data, e);
        return null;
    }
}


