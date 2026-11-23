export type Rgb = readonly [number, number, number];

/** `#rrggbb` to 0–1 channels. Anything else is black. */
export function parseHexColour(hex: string): Rgb {
    const match = /^#?([0-9a-fA-F]{6})$/.exec(hex.trim());
    if (!match) return [0, 0, 0];
    const value = Number.parseInt(match[1]!, 16);
    return [
        (value >> 16) / 255,
        ((value >> 8) & 255) / 255,
        (value & 255) / 255,
    ];
}
