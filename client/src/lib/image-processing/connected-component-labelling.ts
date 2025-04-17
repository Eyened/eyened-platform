export function BlobExtraction(data: Uint8Array, w: number, h: number) {
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
				if (x > 0) stack.push(index - 1);
				if (x < w - 1) stack.push(index + 1);
				if (y > 0) stack.push(index - w);
				if (y < h - 1) stack.push(index + w);
			}
		}
	}
	return label;
}