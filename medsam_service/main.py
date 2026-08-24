from __future__ import annotations

import threading
from pathlib import Path
from typing import Literal

import numpy as np
import torch
import torch.nn.functional as F
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


_MODEL_LOCK = threading.Lock()
_MODEL = None

_MEDSAM_MODEL_PATH = Path("/app/MedSAM/medsam2.pth")
_MEDSAM_CONFIG_NAME = "sam2_hiera_t"
_MEDSAM2_DIR = Path("/app/MedSAM/Medical-SAM2-main")


class ClickPoint(BaseModel):
    x: float
    y: float


class SegmentRequest(BaseModel):
    frame_u8: list[list[int]] = Field(..., description="2D grayscale frame in uint8")
    mode: Literal["area", "layer"] = "area"
    positive_points: list[ClickPoint] = Field(..., min_length=1)
    negative_points: list[ClickPoint] = Field(default_factory=list)
    smoothing_strength: Literal["light", "medium", "strong"] = "medium"
    negative_guard_radius: int = Field(default=6, ge=1, le=64)
    positive_boost_strength: Literal["light", "medium", "strong"] = "strong"
    positive_anchor_radius: int = Field(default=4, ge=1, le=64)


class SegmentResponse(BaseModel):
    mask: list[list[int]]


app = FastAPI(title="MedSAM Service", version="1.0.0")


def _ensure_model():
    global _MODEL
    if _MODEL is not None:
        return _MODEL

    with _MODEL_LOCK:
        if _MODEL is not None:
            return _MODEL

        if not _MEDSAM2_DIR.exists():
            raise FileNotFoundError(
                f"Medical-SAM2-main not found at: {_MEDSAM2_DIR}. "
                "Place the Medical-SAM2-main source under MedSAM/Medical-SAM2-main in this workspace."
            )
        if not _MEDSAM_MODEL_PATH.exists():
            raise FileNotFoundError(f"Model checkpoint not found: {_MEDSAM_MODEL_PATH}")

        import sys

        if str(_MEDSAM2_DIR) not in sys.path:
            sys.path.insert(0, str(_MEDSAM2_DIR))

        import sam2_train  # noqa: F401
        from hydra import compose
        from hydra.utils import instantiate
        from omegaconf import OmegaConf

        cfg = compose(config_name=_MEDSAM_CONFIG_NAME)
        OmegaConf.resolve(cfg)
        model = instantiate(cfg.model, _recursive_=True)

        ckpt = torch.load(str(_MEDSAM_MODEL_PATH), map_location="cpu", weights_only=False)
        state = ckpt["model"] if isinstance(ckpt, dict) and "model" in ckpt else ckpt
        model.load_state_dict(state, strict=False)

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = model.to(device)
        model.eval()

        _MODEL = model
        return _MODEL


def _suppress_negative_neighborhood(mask: np.ndarray, negative_points: list[tuple[float, float]], radius: int) -> np.ndarray:
    if len(negative_points) == 0 or mask.sum() == 0:
        return mask.astype(np.uint8)
    out = mask.astype(np.uint8).copy()
    h, w = out.shape
    r = max(1, int(radius))
    for x, y in negative_points:
        px = int(np.clip(round(x), 0, w - 1))
        py = int(np.clip(round(y), 0, h - 1))
        y0 = max(0, py - r)
        y1 = min(h, py + r + 1)
        x0 = max(0, px - r)
        x1 = min(w, px + r + 1)
        yy, xx = np.ogrid[y0:y1, x0:x1]
        disk = ((yy - py) ** 2 + (xx - px) ** 2) <= (r * r)
        patch = out[y0:y1, x0:x1]
        patch[disk] = 0
        out[y0:y1, x0:x1] = patch
    return out


def _positive_coverage(mask: np.ndarray, positive_points: list[tuple[float, float]], radius: int) -> float:
    if len(positive_points) == 0:
        return 0.0
    h, w = mask.shape
    r = max(1, int(radius))
    covered = 0
    for x, y in positive_points:
        px = int(np.clip(round(x), 0, w - 1))
        py = int(np.clip(round(y), 0, h - 1))
        y0 = max(0, py - r)
        y1 = min(h, py + r + 1)
        x0 = max(0, px - r)
        x1 = min(w, px + r + 1)
        if np.any(mask[y0:y1, x0:x1] > 0):
            covered += 1
    return float(covered) / float(len(positive_points))


def _negative_overlap(mask: np.ndarray, negative_points: list[tuple[float, float]], radius: int) -> float:
    if len(negative_points) == 0:
        return 0.0
    h, w = mask.shape
    r = max(1, int(radius))
    bad = 0
    for x, y in negative_points:
        px = int(np.clip(round(x), 0, w - 1))
        py = int(np.clip(round(y), 0, h - 1))
        y0 = max(0, py - r)
        y1 = min(h, py + r + 1)
        x0 = max(0, px - r)
        x1 = min(w, px + r + 1)
        if np.any(mask[y0:y1, x0:x1] > 0):
            bad += 1
    return float(bad) / float(len(negative_points))


def _smooth_binary(mask: np.ndarray, strength: str) -> np.ndarray:
    if mask.sum() == 0:
        return mask.astype(np.uint8)
    passes = {"light": 1, "medium": 2, "strong": 3}.get(strength, 2)
    t = torch.from_numpy(mask.astype(np.float32)).unsqueeze(0).unsqueeze(0)
    for _ in range(passes):
        t = F.max_pool2d(t, kernel_size=3, stride=1, padding=1)
        t = -F.max_pool2d(-t, kernel_size=3, stride=1, padding=1)
        t = -F.max_pool2d(-t, kernel_size=3, stride=1, padding=1)
        t = F.max_pool2d(t, kernel_size=3, stride=1, padding=1)
    bin_t = (t > 0.5).float()
    nsum = F.avg_pool2d(bin_t, kernel_size=3, stride=1, padding=1) * 9.0
    out = (nsum >= 5.0).float()
    return out.squeeze(0).squeeze(0).cpu().numpy().astype(np.uint8)


def _dense_layer_prompts(
    h: int,
    w: int,
    positive_points: list[tuple[float, float]],
    negative_points: list[tuple[float, float]],
    n_pts: int = 72,
) -> tuple[np.ndarray, np.ndarray]:
    pos = np.asarray(positive_points, dtype=np.float32)
    if pos.shape[0] == 0:
        return np.zeros((0, 2), dtype=np.float32), np.zeros((0,), dtype=np.int32)

    order = np.argsort(pos[:, 0])
    pos = pos[order]

    if len(pos) == 1:
        x_grid = np.linspace(0, w - 1, n_pts, dtype=np.float32)
        y_grid = np.full((n_pts,), float(pos[0, 1]), dtype=np.float32)
    else:
        x_grid = np.linspace(float(pos[:, 0].min()), float(pos[:, 0].max()), n_pts, dtype=np.float32)
        uniq_x, uniq_idx = np.unique(pos[:, 0].astype(np.int32), return_index=True)
        uniq_y = pos[:, 1][uniq_idx]
        if len(uniq_x) <= 1:
            y_grid = np.full((n_pts,), float(uniq_y[0]), dtype=np.float32)
        else:
            y_grid = np.interp(x_grid, uniq_x.astype(np.float32), uniq_y.astype(np.float32)).astype(np.float32)

    dense_pos = np.stack([
        np.clip(x_grid, 0, w - 1),
        np.clip(y_grid, 0, h - 1),
    ], axis=1).astype(np.float32)

    points = [dense_pos]
    labels = [np.ones((dense_pos.shape[0],), dtype=np.int32)]

    if len(negative_points) > 0:
        neg = np.asarray(negative_points, dtype=np.float32)
        points.append(np.clip(neg, [0.0, 0.0], [w - 1.0, h - 1.0]).astype(np.float32))
        labels.append(np.zeros((neg.shape[0],), dtype=np.int32))
    else:
        off = float(max(4, int(0.03 * h)))
        sub = dense_pos[::2]
        neg_up = np.stack([sub[:, 0], np.clip(sub[:, 1] - off, 0, h - 1)], axis=1).astype(np.float32)
        neg_dn = np.stack([sub[:, 0], np.clip(sub[:, 1] + off, 0, h - 1)], axis=1).astype(np.float32)
        points.extend([neg_up, neg_dn])
        labels.extend([
            np.zeros((neg_up.shape[0],), dtype=np.int32),
            np.zeros((neg_dn.shape[0],), dtype=np.int32),
        ])

    return np.concatenate(points, axis=0), np.concatenate(labels, axis=0)


def _centerline_from_points(h: int, w: int, positive_points: list[tuple[float, float]]) -> np.ndarray | None:
    if len(positive_points) == 0:
        return None
    pts = np.asarray(positive_points, dtype=np.float32)
    xs = np.clip(pts[:, 0], 0, w - 1)
    ys = np.clip(pts[:, 1], 0, h - 1)
    x_grid = np.arange(w, dtype=np.float32)
    if len(xs) == 1:
        return np.full((w,), float(ys[0]), dtype=np.float32)
    order = np.argsort(xs)
    xs = xs[order]
    ys = ys[order]
    uniq_x, uniq_idx = np.unique(xs.astype(np.int32), return_index=True)
    uniq_y = ys[uniq_idx]
    if len(uniq_x) <= 1:
        return np.full((w,), float(uniq_y[0]), dtype=np.float32)
    return np.interp(x_grid, uniq_x.astype(np.float32), uniq_y.astype(np.float32)).astype(np.float32)


def _layerify(mask: np.ndarray, prob_map: np.ndarray, positive_points: list[tuple[float, float]]) -> np.ndarray:
    if mask.sum() == 0 or len(positive_points) == 0:
        return mask.astype(np.uint8)

    h, w = mask.shape
    y_center = _centerline_from_points(h, w, positive_points)
    if y_center is None:
        return mask.astype(np.uint8)

    y_spread = float(np.std(np.asarray([p[1] for p in positive_points], dtype=np.float32))) if len(positive_points) > 1 else 0.0
    search_half = max(6, int(round(0.03 * h + min(6.0, 0.4 * y_spread))))
    draw_half = max(2, int(round(0.01 * h)))

    out = np.zeros((h, w), dtype=np.uint8)
    yy = np.arange(h, dtype=np.int32)

    for x in range(w):
        yc = float(y_center[x])
        y0 = max(0, int(round(yc)) - search_half)
        y1 = min(h, int(round(yc)) + search_half + 1)
        if y1 <= y0:
            continue
        y_idx = yy[y0:y1]
        p = prob_map[y0:y1, x]
        d = np.abs(y_idx.astype(np.float32) - yc) / max(1.0, float(search_half))
        score = p - 0.08 * d
        best = int(np.argmax(score))
        y_best = int(y0 + best)
        ys = max(0, y_best - draw_half)
        ye = min(h, y_best + draw_half + 1)
        out[ys:ye, x] = 1

    return (out * (mask > 0).astype(np.uint8)).astype(np.uint8)


def _build_prompt_arrays(
    h: int,
    w: int,
    mode: Literal["area", "layer"],
    positive_points: list[tuple[float, float]],
    negative_points: list[tuple[float, float]],
) -> tuple[np.ndarray, np.ndarray]:
    if mode == "layer":
        return _dense_layer_prompts(h, w, positive_points, negative_points)

    points: list[list[float]] = []
    labels: list[int] = []
    for x, y in positive_points:
        points.append([float(np.clip(x, 0, w - 1)), float(np.clip(y, 0, h - 1))])
        labels.append(1)
    for x, y in negative_points:
        points.append([float(np.clip(x, 0, w - 1)), float(np.clip(y, 0, h - 1))])
        labels.append(0)
    if len(points) == 0:
        return np.zeros((0, 2), dtype=np.float32), np.zeros((0,), dtype=np.int32)
    return np.asarray(points, dtype=np.float32), np.asarray(labels, dtype=np.int32)


@app.get("/health")
def health() -> dict[str, str]:
    # Liveness only: keep compose startup unblocked.
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, str]:
    if not _MEDSAM_MODEL_PATH.exists():
        raise HTTPException(status_code=503, detail=f"Missing checkpoint at {_MEDSAM_MODEL_PATH}")
    if not _MEDSAM2_DIR.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                f"Missing Medical-SAM2-main at {_MEDSAM2_DIR}. "
                "Place the source in MedSAM/Medical-SAM2-main."
            ),
        )
    return {"status": "ready"}


@app.post("/segment", response_model=SegmentResponse)
def segment(body: SegmentRequest) -> SegmentResponse:
    try:
        model = _ensure_model()

        frame = np.asarray(body.frame_u8, dtype=np.uint8)
        if frame.ndim != 2:
            raise ValueError("frame_u8 must be a 2D array")

        h, w = int(frame.shape[0]), int(frame.shape[1])
        rgb = np.repeat(frame[..., None], 3, axis=2).astype(np.uint8)

        positive_points = [(float(p.x), float(p.y)) for p in body.positive_points]
        negative_points = [(float(p.x), float(p.y)) for p in body.negative_points]

        point_coords, point_labels = _build_prompt_arrays(
            h, w, body.mode, positive_points, negative_points
        )
        if point_coords.shape[0] == 0:
            raise ValueError("No valid prompt points were provided")

        from sam2_train.sam2_image_predictor import SAM2ImagePredictor

        predictor = SAM2ImagePredictor(model, mask_threshold=0.0)
        predictor.set_image(rgb)

        with torch.no_grad():
            masks, iou_scores, logits = predictor.predict(
                point_coords=point_coords,
                point_labels=point_labels,
                box=None,
                multimask_output=True,
                return_logits=True,
                normalize_coords=False,
            )

        probs_low = 1.0 / (1.0 + np.exp(-np.clip(logits, -32.0, 32.0)))
        probs_t = torch.from_numpy(probs_low).unsqueeze(1).float()
        probs = F.interpolate(
            probs_t,
            size=(h, w),
            mode="bilinear",
            align_corners=False,
        ).squeeze(1).cpu().numpy()

        boost_scale = {"light": 0.75, "medium": 0.60, "strong": 0.45}.get(
            body.positive_boost_strength, 0.45
        )

        best_mask = np.zeros((h, w), dtype=np.uint8)
        best_score = -1e9

        for k in range(probs.shape[0]):
            prob_map = probs[k]
            base_thr = max(0.02, min(0.60, float(np.percentile(prob_map, 96)) * boost_scale))

            for thr in (0.50, 0.35, 0.22, base_thr):
                candidate = (prob_map >= float(thr)).astype(np.uint8)
                candidate = (candidate * masks[k].astype(np.uint8)).astype(np.uint8)
                if body.mode == "layer":
                    candidate = _layerify(candidate, prob_map, positive_points)
                candidate = _suppress_negative_neighborhood(
                    candidate, negative_points, body.negative_guard_radius
                )
                candidate = _smooth_binary(candidate, body.smoothing_strength)

                pos_cov = _positive_coverage(candidate, positive_points, body.positive_anchor_radius)
                neg_ov = _negative_overlap(candidate, negative_points, max(2, body.negative_guard_radius))
                area_ratio = float(candidate.mean())
                area_penalty = max(0.0, area_ratio - 0.35) * 1.8
                score = float(iou_scores[k]) + 5.0 * pos_cov - 8.0 * neg_ov - area_penalty

                if score > best_score:
                    best_score = score
                    best_mask = candidate

        if best_mask.sum() == 0:
            for x, y in positive_points:
                px = int(np.clip(round(x), 0, w - 1))
                py = int(np.clip(round(y), 0, h - 1))
                best_mask[max(0, py - 1):min(h, py + 2), max(0, px - 1):min(w, px + 2)] = 1

        return SegmentResponse(mask=best_mask.astype(np.uint8).tolist())

    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
