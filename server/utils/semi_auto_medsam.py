from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import os
from pathlib import Path
import threading
import traceback
import uuid
from typing import Any, Literal

import httpxyz
import numpy as np

from eyened_orm import DataRepresentation, Database, Datatype, ImageInstance, Segmentation
from eyened_orm.segmentation_storage import write_segmentation_data


Point = tuple[float, float]


class SemiAutoJobRegistry:
    """In-memory background job tracker for semi-auto MedSAM inference."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, dict[str, Any]] = {}
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="medsam")
        self._redis = None
        try:
            from ..config import get_redis_connection

            self._redis = get_redis_connection()
        except Exception:
            self._redis = None

    @staticmethod
    def _public_view(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "job_id": item["job_id"],
            "status": item["status"],
            "progress": item["progress"],
            "message": item["message"],
            "result": item["result"],
            "error": item["error"],
            "created_at": item["created_at"],
            "updated_at": item["updated_at"],
        }

    @staticmethod
    def _status_key(job_id: str) -> str:
        return f"semi_auto_job:{job_id}"

    def _write_status(self, item: dict[str, Any]) -> None:
        if self._redis is None:
            return
        try:
            payload = json.dumps(self._public_view(item), separators=(",", ":"))
            # Keep job status available for a day for retries/UI refreshes.
            self._redis.setex(self._status_key(item["job_id"]), 24 * 60 * 60, payload)
        except Exception:
            return

    def _read_status(self, job_id: str) -> dict[str, Any] | None:
        if self._redis is None:
            return None
        try:
            raw = self._redis.get(self._status_key(job_id))
            if raw is None:
                return None
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8", errors="ignore")
            data = json.loads(raw)
            if not isinstance(data, dict):
                return None
            return data
        except Exception:
            return None

    def create(self, payload: dict[str, Any]) -> str:
        job_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat() + "Z"
        with self._lock:
            self._jobs[job_id] = {
                "job_id": job_id,
                "status": "queued",
                "progress": 0.0,
                "message": "Queued",
                "result": None,
                "error": None,
                "created_at": now,
                "updated_at": now,
                "payload": payload,
            }
            self._write_status(self._jobs[job_id])
        return job_id

    def start(self, job_id: str) -> None:
        self._executor.submit(self._run, job_id)

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            item = self._jobs.get(job_id)
            if item is None:
                return self._read_status(job_id)
            return self._public_view(item)

    def _update(
        self,
        job_id: str,
        *,
        status: str | None = None,
        progress: float | None = None,
        message: str | None = None,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        with self._lock:
            item = self._jobs.get(job_id)
            if item is None:
                return
            if status is not None:
                item["status"] = status
            if progress is not None:
                item["progress"] = max(0.0, min(1.0, float(progress)))
            if message is not None:
                item["message"] = message
            if result is not None:
                item["result"] = result
            if error is not None:
                item["error"] = error
            item["updated_at"] = datetime.utcnow().isoformat() + "Z"
            self._write_status(item)

    def _run(self, job_id: str) -> None:
        with self._lock:
            item = self._jobs.get(job_id)
            if item is None:
                return
            payload = item["payload"]

        try:
            self._update(job_id, status="running", progress=0.03, message="Loading image")
            segmentation_id = run_medsam_semi_auto(payload, self, job_id)
            self._update(
                job_id,
                status="finished",
                progress=1.0,
                message="Segmentation completed",
                result={"segmentation_id": segmentation_id},
            )
        except Exception as exc:
            self._update(
                job_id,
                status="failed",
                progress=1.0,
                message="Segmentation failed",
                error=f"{exc}\n{traceback.format_exc()}",
            )


JOB_REGISTRY = SemiAutoJobRegistry()


_MODEL_LOCK = threading.Lock()
_MODEL_CACHE: dict[tuple[str, str, str], Any] = {}

# Keep runtime defaults aligned with MedSAM/segmentation.py.
_MEDSAM_MODEL_PATH = "MedSAM/medsam2.pth"
_MEDSAM_CONFIG_NAME = "sam2_hiera_t"


def _medsam_service_url() -> str:
    return os.getenv("EYENED_MEDSAM_URL", "http://medsam:8010").rstrip("/")


def _request_medsam_mask(
    *,
    frame_u8: np.ndarray,
    mode: Literal["area", "layer"],
    positive_points: list[Point],
    negative_points: list[Point],
    smoothing_strength: str,
    negative_guard_radius: int,
    positive_boost_strength: str,
    positive_anchor_radius: int,
) -> np.ndarray:
    body = {
        "frame_u8": frame_u8.astype(np.uint8).tolist(),
        "mode": mode,
        "positive_points": [{"x": float(x), "y": float(y)} for x, y in positive_points],
        "negative_points": [{"x": float(x), "y": float(y)} for x, y in negative_points],
        "smoothing_strength": smoothing_strength,
        "negative_guard_radius": int(negative_guard_radius),
        "positive_boost_strength": positive_boost_strength,
        "positive_anchor_radius": int(positive_anchor_radius),
    }

    endpoint = f"{_medsam_service_url()}/segment"
    with httpxyz.Client(timeout=300.0) as client:
        resp = client.post(endpoint, json=body)
    if resp.status_code != httpxyz.codes.OK:
        detail = ""
        try:
            payload = resp.json()
            detail = str(payload.get("detail", ""))
        except Exception:
            detail = resp.text
        raise RuntimeError(f"MedSAM service request failed ({resp.status_code}): {detail}")

    data = resp.json()
    mask = np.asarray(data.get("mask"), dtype=np.uint8)
    if mask.ndim != 2:
        raise RuntimeError("MedSAM service returned an invalid mask payload")
    return mask


def _require_torch():
    try:
        import torch  # type: ignore
        import torch.nn.functional as F  # type: ignore
    except Exception as exc:
        raise RuntimeError(
            "PyTorch is required for semi-auto MedSAM segmentation. "
            "Install torch in the server image to enable this feature."
        ) from exc
    return torch, F


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _normalize_frame_to_uint8(frame: np.ndarray) -> np.ndarray:
    arr = frame.astype(np.float32)
    finite = np.isfinite(arr)
    if not np.any(finite):
        return np.zeros(arr.shape, dtype=np.uint8)
    vals = arr[finite]
    lo = float(np.percentile(vals, 1.0))
    hi = float(np.percentile(vals, 99.0))
    if hi <= lo:
        lo = float(vals.min())
        hi = float(vals.max())
    if hi <= lo:
        return np.zeros(arr.shape, dtype=np.uint8)
    arr = np.clip((arr - lo) / (hi - lo), 0.0, 1.0)
    return (arr * 255.0).astype(np.uint8)


def _to_oct_frames(pixel: np.ndarray) -> np.ndarray:
    arr = np.asarray(pixel)
    if arr.ndim == 2:
        return arr[None, ...]
    if arr.ndim == 3:
        # If this is color image (H, W, C), collapse channels.
        if arr.shape[-1] <= 4 and arr.shape[0] > 4 and arr.shape[1] > 4:
            return arr.mean(axis=-1, keepdims=False)[None, ...]
        return arr
    if arr.ndim == 4:
        return arr.mean(axis=-1)
    raise ValueError(f"Unsupported image shape for MedSAM: {arr.shape}")


def _suppress_negative_neighborhood(mask: np.ndarray, negative_points: list[Point], radius: int) -> np.ndarray:
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


def _positive_coverage(mask: np.ndarray, positive_points: list[Point], radius: int) -> float:
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


def _negative_overlap(mask: np.ndarray, negative_points: list[Point], radius: int) -> float:
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
    torch, F = _require_torch()
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
    positive_points: list[Point],
    negative_points: list[Point],
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


def _centerline_from_points(h: int, w: int, positive_points: list[Point]) -> np.ndarray | None:
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


def _layerify(mask: np.ndarray, prob_map: np.ndarray, positive_points: list[Point]) -> np.ndarray:
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

    # Keep only points that were inside model-positive region to avoid hallucinated paths.
    return (out * (mask > 0).astype(np.uint8)).astype(np.uint8)


def _build_prompt_arrays(
    h: int,
    w: int,
    mode: Literal["area", "layer"],
    positive_points: list[Point],
    negative_points: list[Point],
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


def _load_medsam_model(model_path: Path, sam_config: str, device: torch.device, progress_cb) -> Any:
    torch, _ = _require_torch()
    key = (str(model_path.resolve()), sam_config, str(device))
    with _MODEL_LOCK:
        cached = _MODEL_CACHE.get(key)
    if cached is not None:
        return cached

    repo_root = _repo_root()
    medsam2_dir = repo_root / "MedSAM" / "Medical-SAM2-main"
    if not medsam2_dir.exists():
        raise FileNotFoundError(f"Medical-SAM2-main not found at: {medsam2_dir}")

    import sys

    if str(medsam2_dir) not in sys.path:
        sys.path.insert(0, str(medsam2_dir))

    progress_cb(0.18, "Loading MedSAM config")
    import sam2_train  # noqa: F401
    from hydra import compose
    from hydra.utils import instantiate
    from omegaconf import OmegaConf

    cfg = compose(config_name=sam_config)
    OmegaConf.resolve(cfg)
    model = instantiate(cfg.model, _recursive_=True)

    progress_cb(0.30, "Loading MedSAM checkpoint")
    ckpt = torch.load(str(model_path), map_location="cpu", weights_only=False)
    state = ckpt["model"] if isinstance(ckpt, dict) and "model" in ckpt else ckpt
    model.load_state_dict(state, strict=False)
    model = model.to(device)
    model.eval()

    with _MODEL_LOCK:
        _MODEL_CACHE[key] = model
    return model


def run_medsam_semi_auto(payload: dict[str, Any], registry: SemiAutoJobRegistry, job_id: str) -> int:
    def progress(p: float, msg: str) -> None:
        registry._update(job_id, progress=p, message=msg)

    image_public_id = str(payload["image_id"])
    feature_id = int(payload["feature_id"])
    creator_id = int(payload["creator_id"])
    subtask_id = payload.get("subtask_id")
    mode: Literal["area", "layer"] = payload.get("mode", "area")

    positive_points: list[Point] = [
        (float(p["x"]), float(p["y"])) for p in payload.get("positive_points", [])
    ]
    negative_points: list[Point] = [
        (float(p["x"]), float(p["y"])) for p in payload.get("negative_points", [])
    ]
    if len(positive_points) == 0:
        raise ValueError("At least one positive point is required")

    negative_guard_radius = int(max(1, payload.get("negative_guard_radius", 6)))
    positive_anchor_radius = int(max(1, payload.get("positive_anchor_radius", 4)))
    positive_boost_strength = str(payload.get("positive_boost_strength", "strong")).lower()
    smoothing_strength = str(payload.get("smoothing_strength", "medium")).lower()

    with Database().get_session() as session:
        image = (
            session.query(ImageInstance)
            .filter(ImageInstance.PublicID == image_public_id)
            .first()
        )
        if image is None and image_public_id.isdigit():
            image = session.get(ImageInstance, int(image_public_id))
        if image is None:
            raise ValueError(f"Image not found: {image_public_id}")

        pixel = image.pixel_array
        frames = _to_oct_frames(pixel)
        depth = int(frames.shape[0])
        h = int(frames.shape[1])
        w = int(frames.shape[2])

        slice_index_raw = payload.get("slice_index")
        if slice_index_raw is None:
            slice_index = 0
        else:
            slice_index = int(slice_index_raw)
        slice_index = int(np.clip(slice_index, 0, depth - 1))

        frame_u8 = _normalize_frame_to_uint8(frames[slice_index])
        progress(0.22, "Sending prompts to MedSAM service")
        best_mask = _request_medsam_mask(
            frame_u8=frame_u8,
            mode=mode,
            positive_points=positive_points,
            negative_points=negative_points,
            smoothing_strength=smoothing_strength,
            negative_guard_radius=negative_guard_radius,
            positive_boost_strength=positive_boost_strength,
            positive_anchor_radius=positive_anchor_radius,
        )

        if best_mask.shape != (h, w):
            raise RuntimeError(
                f"MedSAM service mask shape mismatch: got {best_mask.shape}, expected {(h, w)}"
            )

        if best_mask.sum() == 0:
            # Last-resort visibility fallback at positive clicks.
            for x, y in positive_points:
                px = int(np.clip(round(x), 0, w - 1))
                py = int(np.clip(round(y), 0, h - 1))
                best_mask[max(0, py - 1):min(h, py + 2), max(0, px - 1):min(w, px + 2)] = 1

        progress(0.80, "Saving segmentation")
        segmentation = Segmentation(
            ImageInstanceID=image.ImageInstanceID,
            ImageInstance=image,
            FeatureID=feature_id,
            CreatorID=creator_id,
            SubTaskID=subtask_id,
            DataType=Datatype.R8UI,
            DataRepresentation=DataRepresentation.Binary,
            Depth=depth,
            Height=h,
            Width=w,
            SparseAxis=0 if depth > 1 else None,
            ImageProjectionMatrix=None,
            ScanIndices=[] if depth > 1 else None,
            Threshold=0.5,
            ReferenceSegmentationID=None,
            DateInserted=datetime.now(),
        )

        session.add(segmentation)
        session.flush()

        mask2 = best_mask.astype(np.uint8)
        if depth > 1:
            write_segmentation_data(segmentation, mask2, axis=0, slice_index=slice_index)
        else:
            write_segmentation_data(segmentation, mask2[None, :, :])

        session.commit()
        session.refresh(segmentation)

        progress(0.95, "Finalizing")
        return int(segmentation.SegmentationID)
