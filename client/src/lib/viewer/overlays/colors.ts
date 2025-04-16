import type { Color } from "$lib/utils";

export const colors: Color[] = [
	[0, 82, 204],
	[44, 160, 44],
	[255, 25, 255],
	[8, 203, 189],
	[205, 0, 154],
	[224, 219, 17],
	[0, 204, 82],
	[188, 189, 34],
	[123, 190, 207],
	[61, 0, 204],
	[255, 137, 44],
	[44, 160, 44],
	[158, 92, 0],
	[81, 245, 66],
	[162, 0, 255],
	[255, 0, 0],
	[128, 255, 170],
	[255, 255, 0],
	[125, 34, 236],
	[255, 127, 14],
	[0, 0, 255],
	[0, 128, 0],
	[0, 0, 0],
	[128, 0, 0],
	[0, 128, 128],
	[128, 128, 0],
	[128, 0, 128],
	[192, 192, 192],
	[128, 128, 128],
	[255, 0, 255],
	[255, 255, 255],
	[0, 0, 128],
];

export const colorsFlat = colors.flat().map(c => c / 255);