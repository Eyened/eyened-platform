/** Color-fundus ROI JSON stored on ImageGET.cf_roi. */
export type CfRoiLineSegment = [[number, number], [number, number]];

export type CfRoiLines = {
    top?: CfRoiLineSegment;
    bottom?: CfRoiLineSegment;
    left?: CfRoiLineSegment;
    right?: CfRoiLineSegment;
};

export type CfRoi = {
    center: [number, number];
    radius: number;
    min_x: number;
    max_x: number;
    min_y: number;
    max_y: number;
    lines: CfRoiLines;
    w: number;
    h: number;
};
