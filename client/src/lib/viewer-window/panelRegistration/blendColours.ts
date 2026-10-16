export type Rgb = readonly [number, number, number];

const CYCLE: readonly Rgb[] = [
    [1, 0, 0],
    [0, 1, 0],
    [0, 0, 1],
    [0, 1, 1],
    [1, 0, 1],
    [1, 1, 0],
];

export function blendColours(count: number): { untinted: boolean; colours: Rgb[] } {
    if (count <= 0) return { untinted: false, colours: [] };
    if (count === 1) return { untinted: true, colours: [[1, 1, 1]] };
    if (count === 2) return { untinted: false, colours: [[1, 0, 0], [0, 1, 1]] };
    const colours: Rgb[] = [];
    for (let i = 0; i < count; i++) colours.push(CYCLE[i % CYCLE.length]!);
    return { untinted: false, colours };
}
