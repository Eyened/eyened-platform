export function BlobExtraction(data: Uint8Array, w: number, h: number, connectivity: 4 | 8 = 8) {
    const directions = [
        [-1, 0],
        [1, 0],
        [0, -1],
        [0, 1],
    ];
    if (connectivity == 8) {
        directions.push(
            [-1, -1],
            [-1, 1],
            [1, -1],
            [1, 1],
        );
    }
    const visited = new Uint8Array(data.length);
    const label = new Uint8Array(data.length);

    let i = 0; //component number
    for (let index = 0; index < data.length; index++) {
        if (data[index] && !visited[index]) {
            i++; //found new component
            dfs(index);
        }
    }

    function dfs(index: number) {
        const stack: number[] = [index];
        while (stack.length) {
            const index = stack.pop()!;
            if (visited[index]) continue;
            visited[index] = 1;

            if (data[index]) {
                label[index] = i;
                const x = index % w;
                const y = Math.floor(index / w);
                for (const [dx, dy] of directions) {
                    const x2 = x + dx;
                    const y2 = y + dy;
                    if (x2 >= 0 && x2 < w && y2 >= 0 && y2 < h) {
                        stack.push(index + dx + dy * w);
                    }
                }
            }
        }
    }
    return label;
}