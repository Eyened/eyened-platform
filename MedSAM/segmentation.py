"""
Interactive OCT Annotation Tool with Fine-tuned MedSAM2.

This tool lets you:
    1. Load OCT images from dataset/images.dcm
  2. Click positive (foreground) and negative (background) points on the image
  3. Automatically segment the region using the fine-tuned MedSAM2 model
  4. Save the resulting mask

Usage
-----
    python annotation.py
    python annotation.py --model checkpoints/medsam2_oct_finetuned.pth
    python annotation.py --dicom_file images.dcm
    python annotation.py --image_index 10

Controls
--------
    Left-click    Add a POSITIVE point (foreground — inside the region)
    Right-click   Add a NEGATIVE point (background — outside the region)
    Enter         Run segmentation with current points
    c             Clear all points and the current mask
    n             Next image
    p             Previous image
    s             Save the current mask to annotations/
    q / Esc       Quit
"""

import os
import sys
import argparse
import logging
from collections import deque

import numpy as np
import torch
import torch.nn.functional as F
import pydicom
from PIL import Image
import torchvision.transforms as transforms

# Try to pick an interactive matplotlib backend
import matplotlib
for _backend in ("TkAgg", "Qt5Agg", "Qt4Agg", "GTK3Agg"):
    try:
        matplotlib.use(_backend)
        break
    except Exception:
        continue
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------------
# Path setup – make Medical-SAM2-main importable
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MEDSAM2_DIR = os.path.join(SCRIPT_DIR, "Medical-SAM2-main")
sys.path.insert(0, MEDSAM2_DIR)

import sam2_train  # noqa: F401  (triggers hydra init)
from hydra import compose
from hydra.utils import instantiate
from omegaconf import OmegaConf
from sam2_train.sam2_image_predictor import SAM2ImagePredictor


def _normalize_frame_to_uint8(frame: np.ndarray, invert: bool = False) -> np.ndarray:
    """Normalize a single DICOM frame to uint8 using robust percentile windowing."""
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
    if invert:
        arr = 1.0 - arr
    return (arr * 255.0).astype(np.uint8)


def load_oct_dicom_images(dicom_path: str) -> np.ndarray:
    """Load OCT frames from DICOM and return (N, H, W) uint8 images."""
    ds = pydicom.dcmread(dicom_path)
    pixel = ds.pixel_array

    slope = float(getattr(ds, "RescaleSlope", 1.0))
    intercept = float(getattr(ds, "RescaleIntercept", 0.0))
    pixel = pixel.astype(np.float32) * slope + intercept

    # Normalize dimensionality to (N, H, W) grayscale.
    if pixel.ndim == 2:
        pixel = pixel[None, ...]
    elif pixel.ndim == 3:
        # Typical OCT multi-frame is already (N, H, W).
        pass
    elif pixel.ndim == 4:
        # Handle RGB-like shapes by converting channels to grayscale.
        pixel = pixel.mean(axis=-1)
    else:
        raise ValueError(f"Unsupported DICOM pixel array shape: {pixel.shape}")

    photometric = str(getattr(ds, "PhotometricInterpretation", "MONOCHROME2")).upper()
    invert = photometric == "MONOCHROME1"

    frames = [_normalize_frame_to_uint8(frame, invert=invert) for frame in pixel]
    images = np.stack(frames, axis=0).astype(np.uint8)
    return images


# ---------------------------------------------------------------------------
# Interactive annotator
# ---------------------------------------------------------------------------
class OCTAnnotator:
    """Click-to-segment OCT images with a fine-tuned MedSAM2 model."""

    def __init__(self, model, images, device="cuda", image_size=1024,
                 output_dir="annotations", smoothing_strength="medium",
                 negative_guard_radius=6, positive_boost_strength="strong",
                 positive_anchor_radius=4):
        self.model = model
        self.predictor = SAM2ImagePredictor(model, mask_threshold=0.0)
        self.images = images
        self.device = device
        self.image_size = image_size
        self.output_dir = output_dir
        self.smoothing_strength = str(smoothing_strength).lower()
        self.negative_guard_radius = int(max(1, negative_guard_radius))
        self.positive_boost_strength = str(positive_boost_strength).lower()
        self.positive_anchor_radius = int(max(1, positive_anchor_radius))
        os.makedirs(output_dir, exist_ok=True)

        self.current_idx = 0
        self.positive_points = []   # (x, y) in display space
        self.negative_points = []
        self.current_mask = None    # (H, W) binary numpy array
        self.iou_score = None

        # Cached image-encoder features (recomputed on image change)
        self.image_embed = None
        self.high_res_feats = None

        # --- matplotlib figure ---
        self.fig, self.ax = plt.subplots(1, 1, figsize=(12, 7))
        try:
            self.fig.canvas.manager.set_window_title("MedSAM2 OCT Annotator")
        except Exception:
            pass
        self.fig.canvas.mpl_connect("button_press_event", self._on_click)
        self.fig.canvas.mpl_connect("key_press_event", self._on_key)

    # ------------------------------------------------------------------
    # Image encoding (cached per image)
    # ------------------------------------------------------------------
    def _encode_image(self, idx):
        """Compute and cache predictor state for one image."""
        img = self.images[idx]
        img_rgb = np.repeat(img[..., None], 3, axis=2).astype(np.uint8)
        self.predictor.set_image(img_rgb)
        self.image_embed = True
        self.high_res_feats = True

    def _point_is_inside_mask(self, mask, x, y):
        """Check if a point lies in a binary mask."""
        h, w = mask.shape
        px = int(np.clip(round(x), 0, w - 1))
        py = int(np.clip(round(y), 0, h - 1))
        return bool(mask[py, px] > 0)

    def _restrict_to_positive_band(self, mask, positive_points, band_ratio=0.06):
        """Keep mask near a smooth layer centerline inferred from positive clicks."""
        if len(positive_points) == 0 or mask.sum() == 0:
            return mask

        h, w = mask.shape
        margin = max(6, int(h * band_ratio))

        pts = np.array(positive_points, dtype=np.float32)
        xs = np.clip(pts[:, 0], 0, w - 1)
        ys = np.clip(pts[:, 1], 0, h - 1)

        # If we only have one click, fall back to a horizontal strip around that y.
        if len(xs) == 1:
            yc = int(round(float(ys[0])))
            y0 = max(0, yc - margin)
            y1 = min(h, yc + margin + 1)
            band = np.zeros((h, w), dtype=np.uint8)
            band[y0:y1, :] = 1
            return (mask.astype(np.uint8) * band).astype(np.uint8)

        # Build a smooth per-column centerline by interpolating positive clicks.
        order = np.argsort(xs)
        xs_sorted = xs[order]
        ys_sorted = ys[order]

        uniq_x, uniq_idx = np.unique(xs_sorted.astype(np.int32), return_index=True)
        uniq_y = ys_sorted[uniq_idx]

        x_grid = np.arange(w, dtype=np.float32)
        y_center = np.interp(x_grid, uniq_x.astype(np.float32), uniq_y)

        # Slightly widen margin when clicks are spread across multiple nearby layers.
        y_spread = float(np.std(ys)) if len(ys) > 1 else 0.0
        adaptive_margin = int(round(margin + min(8.0, 0.5 * y_spread)))

        yy = np.arange(h, dtype=np.float32)[:, None]
        band = (np.abs(yy - y_center[None, :]) <= adaptive_margin).astype(np.uint8)
        return (mask.astype(np.uint8) * band).astype(np.uint8)

    def _suppress_negative_neighborhood(self, mask, negative_points, radius=4):
        """Remove pixels around negative clicks to discourage overlap with wrong layers."""
        if len(negative_points) == 0 or mask.sum() == 0:
            return mask

        h, w = mask.shape
        out = mask.copy().astype(np.uint8)
        for x, y in negative_points:
            px = int(np.clip(round(x), 0, w - 1))
            py = int(np.clip(round(y), 0, h - 1))
            y0 = max(0, py - radius)
            y1 = min(h, py + radius + 1)
            x0 = max(0, px - radius)
            x1 = min(w, px + radius + 1)
            patch = out[y0:y1, x0:x1]
            yy, xx = np.ogrid[y0:y1, x0:x1]
            disk = ((yy - py) ** 2 + (xx - px) ** 2) <= (radius ** 2)
            patch[disk] = 0
            out[y0:y1, x0:x1] = patch
        return out

    def _negative_overlap_ratio(self, mask, negative_points, radius=2):
        """Return fraction of negative points whose neighborhood overlaps the mask."""
        if len(negative_points) == 0:
            return 0.0
        H, W = mask.shape
        overlap_hits = 0
        for nx, ny in negative_points:
            px = int(np.clip(round(nx), 0, W - 1))
            py = int(np.clip(round(ny), 0, H - 1))
            y0 = max(0, py - radius)
            y1 = min(H, py + radius + 1)
            x0 = max(0, px - radius)
            x1 = min(W, px + radius + 1)
            if np.any(mask[y0:y1, x0:x1] > 0):
                overlap_hits += 1
        return float(overlap_hits) / float(len(negative_points))

    def _positive_coverage_ratio(self, mask, positive_points, radius=5):
        """Return fraction of positive points whose neighborhood is covered by the mask."""
        if len(positive_points) == 0:
            return 0.0
        H, W = mask.shape
        covered = 0
        for px_raw, py_raw in positive_points:
            px = int(np.clip(round(px_raw), 0, W - 1))
            py = int(np.clip(round(py_raw), 0, H - 1))
            y0 = max(0, py - radius)
            y1 = min(H, py + radius + 1)
            x0 = max(0, px - radius)
            x1 = min(W, px + radius + 1)
            if np.any(mask[y0:y1, x0:x1] > 0):
                covered += 1
        return float(covered) / float(len(positive_points))

    def _boost_positive_regions(self, mask, prob_map, positive_points, negative_points):
        """Recover missed neighborhoods around positive clicks while respecting negatives."""
        if len(positive_points) == 0:
            return mask

        H, W = prob_map.shape
        out = mask.astype(np.uint8).copy()

        boost_mode = self.positive_boost_strength
        if boost_mode not in ("light", "medium", "strong"):
            boost_mode = "strong"
        boost_cfg = {
            "light": {"skip_radius": 4, "band_ratio": 0.08, "seed_scale": 0.30},
            "medium": {"skip_radius": 3, "band_ratio": 0.10, "seed_scale": 0.40},
            "strong": {"skip_radius": 2, "band_ratio": 0.12, "seed_scale": 0.50},
        }[boost_mode]

        for x, y in positive_points:
            px = int(np.clip(round(x), 0, W - 1))
            py = int(np.clip(round(y), 0, H - 1))

            # Skip if this positive click is already covered in a small neighborhood.
            sr = int(boost_cfg["skip_radius"])
            y0 = max(0, py - sr)
            y1 = min(H, py + sr + 1)
            x0 = max(0, px - sr)
            x1 = min(W, px + sr + 1)
            if np.any(out[y0:y1, x0:x1] > 0):
                continue

            seed_thr = max(0.01, min(0.18, float(prob_map[py, px]) * boost_cfg["seed_scale"]))
            grow = self._grow_region_from_seed(prob_map, px, py, seed_thr)
            grow = self._restrict_to_positive_band(grow, positive_points, band_ratio=boost_cfg["band_ratio"])
            grow = self._suppress_negative_neighborhood(
                grow, negative_points, radius=self.negative_guard_radius
            )
            out = np.maximum(out, grow).astype(np.uint8)

        out = self._force_positive_anchors(out, prob_map, positive_points, negative_points)

        out = self._extract_positive_component(out, positive_points, prob_map=prob_map)
        return out

    def _force_positive_anchors(self, mask, prob_map, positive_points, negative_points):
        """Guarantee every positive point neighborhood is covered unless blocked by negatives."""
        if len(positive_points) == 0:
            return mask

        H, W = prob_map.shape
        out = mask.astype(np.uint8).copy()
        anchor_r = int(max(2, self.positive_anchor_radius))

        for _ in range(2):
            changed = False
            for x, y in positive_points:
                px = int(np.clip(round(x), 0, W - 1))
                py = int(np.clip(round(y), 0, H - 1))

                y0 = max(0, py - anchor_r)
                y1 = min(H, py + anchor_r + 1)
                x0 = max(0, px - anchor_r)
                x1 = min(W, px + anchor_r + 1)
                if np.any(out[y0:y1, x0:x1] > 0):
                    continue

                seed_thr = max(0.005, min(0.16, float(prob_map[py, px]) * 0.25))
                grow = self._grow_region_from_seed(prob_map, px, py, seed_thr)
                grow = self._restrict_to_positive_band(
                    grow, positive_points, band_ratio=0.10
                )
                grow = self._suppress_negative_neighborhood(
                    grow, negative_points, radius=self.negative_guard_radius
                )
                out = np.maximum(out, grow).astype(np.uint8)
                changed = True

            out = self._suppress_negative_neighborhood(
                out, negative_points, radius=self.negative_guard_radius
            )
            if not changed:
                break

        return out

    def _collect_point_intensities(self, img, points, patch_radius=2):
        """Collect local intensity samples around click points."""
        if len(points) == 0:
            return np.array([], dtype=np.float32)

        h, w = img.shape
        vals = []
        for x, y in points:
            px = int(np.clip(round(x), 0, w - 1))
            py = int(np.clip(round(y), 0, h - 1))
            y0 = max(0, py - patch_radius)
            y1 = min(h, py + patch_radius + 1)
            x0 = max(0, px - patch_radius)
            x1 = min(w, px + patch_radius + 1)
            vals.append(img[y0:y1, x0:x1].reshape(-1))
        return np.concatenate(vals).astype(np.float32)

    def _robust_point_intensity_stats(self, img, points, patch_radius=4):
        """Compute robust mean/std from larger click neighborhoods."""
        vals = self._collect_point_intensities(img, points, patch_radius=patch_radius)
        if vals.size == 0:
            return None

        lo, hi = np.percentile(vals, [15.0, 85.0])
        core = vals[(vals >= lo) & (vals <= hi)]
        if core.size < 8:
            core = vals

        mean = float(np.mean(core))
        std = float(np.std(core))
        med = float(np.median(core))
        return {"mean": mean, "std": std, "median": med}

    def _smooth_binary_mask(self, mask):
        """Smooth jagged mask edges while preserving thin-layer structure."""
        if mask.sum() == 0:
            return mask

        t = torch.from_numpy(mask.astype(np.float32)).unsqueeze(0).unsqueeze(0)

        strength = self.smoothing_strength
        if strength not in ("light", "medium", "strong"):
            strength = "medium"

        passes = {"light": 1, "medium": 2, "strong": 3}[strength]
        for _ in range(passes):
            # Morphological close (dilate->erode) then open (erode->dilate)
            t = F.max_pool2d(t, kernel_size=3, stride=1, padding=1)
            t = -F.max_pool2d(-t, kernel_size=3, stride=1, padding=1)
            t = -F.max_pool2d(-t, kernel_size=3, stride=1, padding=1)
            t = F.max_pool2d(t, kernel_size=3, stride=1, padding=1)

        # Majority voting in 3x3 neighborhood to suppress isolated spikes/holes.
        bin_t = (t > 0.5).float()
        nsum = F.avg_pool2d(bin_t, kernel_size=3, stride=1, padding=1) * 9.0
        out = (nsum >= 5.0).float()
        return out.squeeze(0).squeeze(0).cpu().numpy().astype(np.uint8)

    def _shrink_large_mask(self, mask, prob_map, positive_points, max_ratio=0.12):
        """Shrink overly large masks by raising probability cutoff while preserving positive anchor."""
        if mask.sum() == 0:
            return mask

        h, w = mask.shape
        if float(mask.mean()) <= max_ratio:
            return mask

        masked_probs = prob_map[mask > 0]
        if masked_probs.size == 0:
            return mask

        for q in (50, 60, 70, 80, 90, 95):
            thr = float(np.percentile(masked_probs, q))
            candidate = ((prob_map >= thr).astype(np.uint8) * mask.astype(np.uint8)).astype(np.uint8)
            candidate = self._extract_positive_component(candidate, positive_points, prob_map=prob_map)
            if candidate.sum() > 0 and float(candidate.mean()) <= max_ratio:
                return candidate

        return mask

    def _refine_layer_mask(self, mask, prob_map, positive_points, negative_points, img):
        """Refine a candidate toward the clicked OCT layer using intensity and negative clicks."""
        if mask.sum() == 0:
            return mask

        candidate = mask.astype(np.uint8)
        candidate = self._restrict_to_positive_band(candidate, positive_points)
        candidate = self._suppress_negative_neighborhood(candidate, negative_points, radius=4)

        pos_stats = self._robust_point_intensity_stats(img, positive_points, patch_radius=4)
        neg_stats = self._robust_point_intensity_stats(img, negative_points, patch_radius=4)

        if pos_stats is not None:
            pos_mean = pos_stats["mean"]
            pos_std = pos_stats["std"]
            tol = max(8.0, 2.4 * pos_std)
            intensity_ok = np.abs(img.astype(np.float32) - pos_mean) <= tol

            if neg_stats is not None:
                neg_mean = neg_stats["mean"]
                d_pos = np.abs(img.astype(np.float32) - pos_mean)
                d_neg = np.abs(img.astype(np.float32) - neg_mean)
                # Keep pixels whose intensity is closer to positive clicks than negatives.
                intensity_ok = intensity_ok & (d_pos <= d_neg)

            candidate = (candidate * intensity_ok.astype(np.uint8)).astype(np.uint8)

        candidate = self._extract_positive_component(candidate, positive_points, prob_map=prob_map)
        candidate = self._shrink_large_mask(candidate, prob_map, positive_points, max_ratio=0.14)
        candidate = self._suppress_negative_neighborhood(candidate, negative_points, radius=5)
        candidate = self._enforce_thin_layer_geometry(
            candidate, prob_map, positive_points, negative_points
        )
        candidate = self._suppress_negative_neighborhood(
            candidate, negative_points, radius=self.negative_guard_radius + 1
        )
        candidate = self._smooth_binary_mask(candidate)
        candidate = self._boost_positive_regions(candidate, prob_map, positive_points, negative_points)
        candidate = self._suppress_negative_neighborhood(
            candidate, negative_points, radius=self.negative_guard_radius + 1
        )
        candidate = self._force_positive_anchors(
            candidate, prob_map, positive_points, negative_points
        )
        candidate = self._extract_positive_component(candidate, positive_points, prob_map=prob_map)
        return candidate

    def _enforce_prompt_hard_constraints(self, mask, prob_map, positive_points, negative_points):
        """Apply strict prompt constraints: keep positives, exclude negatives."""
        if mask.sum() == 0:
            return mask

        candidate = mask.astype(np.uint8)
        candidate = self._restrict_to_positive_band(candidate, positive_points, band_ratio=0.06)

        # Escalate suppression until negative points are excluded.
        for radius in (3, 5, 7, 9):
            if not self._hits_negative_point(candidate, negative_points):
                break
            candidate = self._suppress_negative_neighborhood(candidate, negative_points, radius=radius)
            candidate = self._extract_positive_component(candidate, positive_points, prob_map=prob_map)

        # If positive points are missing after suppression, regrow around each positive click.
        if candidate.sum() > 0:
            H, W = candidate.shape
            for x, y in positive_points:
                px = int(np.clip(round(x), 0, W - 1))
                py = int(np.clip(round(y), 0, H - 1))
                if candidate[py, px] == 0:
                    seed_thr = max(0.01, float(prob_map[py, px]) * 0.30)
                    grow = self._grow_region_from_seed(prob_map, px, py, seed_thr)
                    grow = self._restrict_to_positive_band(grow, positive_points, band_ratio=0.06)
                    grow = self._suppress_negative_neighborhood(grow, negative_points, radius=8)
                    candidate = ((candidate + grow) > 0).astype(np.uint8)
                    candidate = self._extract_positive_component(candidate, positive_points, prob_map=prob_map)

        # Final strict cleanup.
        if self._hits_negative_point(candidate, negative_points):
            candidate = self._suppress_negative_neighborhood(candidate, negative_points, radius=10)
            candidate = self._extract_positive_component(candidate, positive_points, prob_map=prob_map)

        candidate = self._enforce_thin_layer_geometry(
            candidate, prob_map, positive_points, negative_points
        )
        candidate = self._suppress_negative_neighborhood(
            candidate, negative_points, radius=self.negative_guard_radius + 1
        )
        candidate = self._boost_positive_regions(candidate, prob_map, positive_points, negative_points)
        candidate = self._suppress_negative_neighborhood(
            candidate, negative_points, radius=self.negative_guard_radius + 1
        )
        candidate = self._force_positive_anchors(
            candidate, prob_map, positive_points, negative_points
        )

        return candidate

    def _centerline_from_positive_points(self, h, w, positive_points):
        """Interpolate a smooth centerline from positive clicks."""
        if len(positive_points) == 0:
            return None

        pts = np.asarray(positive_points, dtype=np.float32)
        xs = np.clip(pts[:, 0], 0, w - 1)
        ys = np.clip(pts[:, 1], 0, h - 1)
        x_grid = np.arange(w, dtype=np.float32)

        if len(xs) == 1:
            return np.full((w,), float(ys[0]), dtype=np.float32)

        order = np.argsort(xs)
        xs_sorted = xs[order]
        ys_sorted = ys[order]
        uniq_x, uniq_idx = np.unique(xs_sorted.astype(np.int32), return_index=True)
        uniq_y = ys_sorted[uniq_idx]

        if len(uniq_x) <= 1:
            return np.full((w,), float(uniq_y[0]), dtype=np.float32)

        return np.interp(x_grid, uniq_x.astype(np.float32), uniq_y.astype(np.float32)).astype(np.float32)

    def _enforce_thin_layer_geometry(self, mask, prob_map, positive_points, negative_points):
        """Constrain mask to a thin centerline-following layer and remove off-layer spill."""
        if mask.sum() == 0 or len(positive_points) == 0:
            return mask

        candidate = mask.astype(np.uint8)
        H, W = candidate.shape
        y_center = self._centerline_from_positive_points(H, W, positive_points)
        if y_center is None:
            return candidate

        pos_ys = np.asarray([p[1] for p in positive_points], dtype=np.float32)
        y_spread = float(np.std(pos_ys)) if len(pos_ys) > 1 else 0.0
        half_thick = max(5, int(round(0.024 * H + min(6.0, 0.40 * y_spread))))

        yy = np.arange(H, dtype=np.float32)[:, None]
        band = (np.abs(yy - y_center[None, :]) <= float(half_thick)).astype(np.uint8)
        candidate = (candidate * band).astype(np.uint8)
        if candidate.sum() == 0:
            return candidate

        # Per-column, keep only the run closest to the centerline.
        for x in range(W):
            col = candidate[:, x]
            idx = np.where(col > 0)[0]
            if idx.size <= 1:
                continue

            split = np.where(np.diff(idx) > 1)[0]
            starts = np.concatenate([idx[:1], idx[split + 1]])
            ends = np.concatenate([idx[split], idx[-1:]])

            yc = float(y_center[x])
            best_run = -1
            best_score = 1e18
            for r, (s, e) in enumerate(zip(starts, ends)):
                mid = 0.5 * (float(s) + float(e))
                run_len = float(e - s + 1)
                run_prob = float(np.mean(prob_map[int(s):int(e) + 1, x]))
                score = abs(mid - yc) + 0.08 * abs(run_len - (2.0 * half_thick)) - 0.8 * run_prob
                if score < best_score:
                    best_score = score
                    best_run = r

            keep = np.zeros_like(col)
            if best_run >= 0:
                s = int(starts[best_run])
                e = int(ends[best_run])
                keep[s:e + 1] = 1
            candidate[:, x] = keep

        candidate = self._suppress_negative_neighborhood(candidate, negative_points, radius=6)
        candidate = self._extract_positive_component(candidate, positive_points, prob_map=prob_map)
        candidate = self._recover_undersegmented_layer(
            candidate, prob_map, positive_points, negative_points, base_half_thick=half_thick
        )
        candidate = self._complete_layer_continuity(
            candidate, prob_map, positive_points, negative_points
        )
        candidate = self._connect_positive_anchors(
            candidate, prob_map, positive_points, negative_points
        )
        return candidate

    def _recover_undersegmented_layer(
        self, mask, prob_map, positive_points, negative_points, base_half_thick=5
    ):
        """Regrow thin masks along centerline when strict pruning removes too much tissue."""
        if len(positive_points) == 0:
            return mask

        H, W = prob_map.shape
        candidate = mask.astype(np.uint8)
        min_target = max(140, int(0.0018 * H * W))
        if candidate.sum() >= min_target:
            return candidate

        y_center = self._centerline_from_positive_points(H, W, positive_points)
        if y_center is None:
            return candidate

        relaxed_half = int(base_half_thick + max(5, int(0.03 * H)))
        yy = np.arange(H, dtype=np.float32)[:, None]
        relaxed_band = (np.abs(yy - y_center[None, :]) <= float(relaxed_half)).astype(np.uint8)

        if candidate.sum() > 0:
            pvals = prob_map[candidate > 0]
            thr = float(np.percentile(pvals, 22)) if pvals.size > 0 else 0.06
            thr = max(0.03, min(0.25, thr))
        else:
            pos_p = []
            for x, y in positive_points:
                px = int(np.clip(round(x), 0, W - 1))
                py = int(np.clip(round(y), 0, H - 1))
                pos_p.append(float(prob_map[py, px]))
            seed_p = float(np.mean(pos_p)) if len(pos_p) > 0 else 0.12
            thr = max(0.03, min(0.22, 0.45 * seed_p))

        grown = ((prob_map >= thr).astype(np.uint8) * relaxed_band).astype(np.uint8)
        grown = self._extract_positive_component(grown, positive_points, prob_map=prob_map)
        grown = self._suppress_negative_neighborhood(grown, negative_points, radius=5)
        grown = self._extract_positive_component(grown, positive_points, prob_map=prob_map)
        grown = self._complete_layer_continuity(
            grown, prob_map, positive_points, negative_points
        )

        if grown.sum() > candidate.sum() and not self._hits_negative_point(grown, negative_points):
            return grown
        return candidate

    def _complete_layer_continuity(self, mask, prob_map, positive_points, negative_points):
        """Complete fragmented masks by tracing a continuous layer path across columns."""
        if len(positive_points) == 0:
            return mask

        H, W = prob_map.shape
        y_center = self._centerline_from_positive_points(H, W, positive_points)
        if y_center is None:
            return mask

        candidate = mask.astype(np.uint8)
        cover_before = float(np.mean(candidate.sum(axis=0) > 0)) if candidate.sum() > 0 else 0.0
        if cover_before >= 0.85:
            return candidate

        pos_vals = []
        for x, y in positive_points:
            px = int(np.clip(round(x), 0, W - 1))
            py = int(np.clip(round(y), 0, H - 1))
            pos_vals.append(float(prob_map[py, px]))
        p_ref = float(np.median(pos_vals)) if len(pos_vals) > 0 else 0.15

        search_half = max(8, int(0.05 * H))
        draw_half = max(3, int(0.012 * H))
        p_thr = max(0.02, min(0.22, 0.40 * p_ref))

        path_mask = np.zeros((H, W), dtype=np.uint8)
        yy = np.arange(H, dtype=np.float32)
        for x in range(W):
            yc = float(y_center[x])
            y0 = max(0, int(round(yc)) - search_half)
            y1 = min(H, int(round(yc)) + search_half + 1)
            if y1 <= y0:
                continue

            y_win = yy[y0:y1]
            p_win = prob_map[y0:y1, x]
            dist = np.abs(y_win - yc) / max(1.0, float(search_half))
            score = p_win - 0.08 * dist

            best_local = int(np.argmax(score))
            y_best = int(y0 + best_local)
            if float(prob_map[y_best, x]) < p_thr:
                continue

            ys = max(0, y_best - draw_half)
            ye = min(H, y_best + draw_half + 1)
            path_mask[ys:ye, x] = 1

        grown = np.maximum(candidate, path_mask).astype(np.uint8)
        grown = self._restrict_to_positive_band(grown, positive_points, band_ratio=0.08)
        grown = self._suppress_negative_neighborhood(grown, negative_points, radius=4)
        grown = self._extract_positive_component(grown, positive_points, prob_map=prob_map)

        cover_after = float(np.mean(grown.sum(axis=0) > 0)) if grown.sum() > 0 else 0.0
        if cover_after > cover_before and not self._hits_negative_point(grown, negative_points):
            return grown
        return candidate

    def _connect_positive_anchors(self, mask, prob_map, positive_points, negative_points):
        """Force a connected layer path through positive anchors."""
        if len(positive_points) < 2:
            return mask

        H, W = prob_map.shape
        candidate = mask.astype(np.uint8).copy()
        y_center = self._centerline_from_positive_points(H, W, positive_points)
        if y_center is None:
            return candidate

        pts = np.asarray(positive_points, dtype=np.float32)
        pts = pts[np.argsort(pts[:, 0])]

        search_half = max(6, int(0.035 * H))
        draw_half = max(2, int(0.010 * H))

        anchors = []
        for x_raw, y_raw in pts:
            px = int(np.clip(round(x_raw), 0, W - 1))
            py_hint = int(np.clip(round(y_raw), 0, H - 1))

            yc = int(np.clip(round(float(y_center[px])), 0, H - 1))
            y0 = max(0, min(py_hint, yc) - search_half)
            y1 = min(H, max(py_hint, yc) + search_half + 1)
            if y1 <= y0:
                anchors.append((px, py_hint))
                continue

            y_win = np.arange(y0, y1, dtype=np.float32)
            p_win = prob_map[y0:y1, px]
            dist_click = np.abs(y_win - float(py_hint)) / max(1.0, float(search_half))
            dist_ctr = np.abs(y_win - float(yc)) / max(1.0, float(search_half))
            score = p_win - 0.06 * dist_click - 0.05 * dist_ctr
            y_best = int(y0 + int(np.argmax(score)))
            anchors.append((px, y_best))

        bridge = np.zeros((H, W), dtype=np.uint8)
        for i in range(len(anchors) - 1):
            x0, y0 = anchors[i]
            x1, y1 = anchors[i + 1]

            if x0 == x1:
                ys = min(y0, y1)
                ye = max(y0, y1)
                bridge[max(0, ys - draw_half):min(H, ye + draw_half + 1), x0] = 1
                continue

            x_step = 1 if x1 > x0 else -1
            span = abs(x1 - x0)
            for t, x in enumerate(range(x0, x1 + x_step, x_step)):
                alpha = float(t) / float(max(1, span))
                y_lin = (1.0 - alpha) * float(y0) + alpha * float(y1)
                yc = float(y_center[int(np.clip(x, 0, W - 1))])

                y_mid = int(round(0.6 * y_lin + 0.4 * yc))
                wy0 = max(0, y_mid - search_half)
                wy1 = min(H, y_mid + search_half + 1)
                if wy1 <= wy0:
                    continue

                y_win = np.arange(wy0, wy1, dtype=np.float32)
                p_win = prob_map[wy0:wy1, x]
                dist = np.abs(y_win - y_mid) / max(1.0, float(search_half))
                score = p_win - 0.05 * dist
                y_best = int(wy0 + int(np.argmax(score)))

                ys = max(0, y_best - draw_half)
                ye = min(H, y_best + draw_half + 1)
                bridge[ys:ye, x] = 1

        grown = np.maximum(candidate, bridge).astype(np.uint8)
        grown = self._restrict_to_positive_band(grown, positive_points, band_ratio=0.09)
        grown = self._suppress_negative_neighborhood(
            grown, negative_points, radius=self.negative_guard_radius
        )
        grown = self._extract_positive_component(grown, positive_points, prob_map=prob_map)
        return grown

    # ------------------------------------------------------------------
    # Segmentation
    # ------------------------------------------------------------------
    def _extract_positive_component(self, mask, positive_points, prob_map=None):
        """Keep only the connected component that contains (or is closest to) a positive point."""
        if len(positive_points) == 0 or mask.sum() == 0:
            return mask

        H, W = mask.shape
        visited = np.zeros((H, W), dtype=bool)
        comp_union = np.zeros((H, W), dtype=np.uint8)

        for x, y in positive_points:
            px = int(np.clip(round(x), 0, W - 1))
            py = int(np.clip(round(y), 0, H - 1))

            if mask[py, px] == 0:
                # If click is outside binary mask, snap to nearest foreground pixel.
                if prob_map is None:
                    continue
                fg = np.argwhere(mask > 0)
                if len(fg) == 0:
                    continue
                d2 = (fg[:, 0] - py) ** 2 + (fg[:, 1] - px) ** 2
                nearest = fg[int(np.argmin(d2))]
                py, px = int(nearest[0]), int(nearest[1])

            if visited[py, px]:
                continue

            comp = np.zeros((H, W), dtype=np.uint8)
            q = deque()
            q.append((py, px))
            visited[py, px] = True

            while q:
                cy, cx = q.popleft()
                comp[cy, cx] = 1
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                    if 0 <= ny < H and 0 <= nx < W and not visited[ny, nx] and mask[ny, nx] == 1:
                        visited[ny, nx] = True
                        q.append((ny, nx))

            comp_union = np.maximum(comp_union, comp)

        if comp_union.sum() > 0:
            return comp_union
        return mask

    def _grow_region_from_seed(self, prob_map, seed_x, seed_y, threshold):
        """Grow a connected region from one seed using a probability threshold."""
        H, W = prob_map.shape
        sx = int(np.clip(round(seed_x), 0, W - 1))
        sy = int(np.clip(round(seed_y), 0, H - 1))

        if prob_map[sy, sx] < threshold:
            return np.zeros((H, W), dtype=np.uint8)

        region = np.zeros((H, W), dtype=np.uint8)
        visited = np.zeros((H, W), dtype=bool)
        q = deque([(sy, sx)])
        visited[sy, sx] = True

        while q:
            cy, cx = q.popleft()
            if prob_map[cy, cx] < threshold:
                continue
            region[cy, cx] = 1
            for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)):
                if 0 <= ny < H and 0 <= nx < W and not visited[ny, nx]:
                    visited[ny, nx] = True
                    q.append((ny, nx))

        return region

    def _hits_negative_point(self, mask, negative_points):
        """Return True if mask covers any negative click."""
        if len(negative_points) == 0:
            return False
        H, W = mask.shape
        for nx, ny in negative_points:
            npx = int(np.clip(round(nx), 0, W - 1))
            npy = int(np.clip(round(ny), 0, H - 1))
            if mask[npy, npx] == 1:
                return True
        return False

    def _auto_box_from_points(self, h, w, positive_points, negative_points):
        """Build an XYXY prompt box from positive clicks with safety margin."""
        if len(positive_points) == 0:
            return None

        pts = np.asarray(positive_points, dtype=np.float32)
        x_min = float(np.min(pts[:, 0]))
        x_max = float(np.max(pts[:, 0]))
        y_min = float(np.min(pts[:, 1]))
        y_max = float(np.max(pts[:, 1]))

        span_x = max(8.0, x_max - x_min)
        span_y = max(8.0, y_max - y_min)
        margin_x = max(10.0, 0.25 * span_x)
        margin_y = max(8.0, 0.20 * span_y)

        if len(positive_points) == 1:
            # Single click: encourage thin horizontal structure around the point.
            margin_x = max(margin_x, 0.40 * w)
            margin_y = max(margin_y, 0.08 * h)

        x0 = x_min - margin_x
        x1 = x_max + margin_x
        y0 = y_min - margin_y
        y1 = y_max + margin_y

        # Keep obvious negatives outside the box when possible.
        for nx, ny in negative_points:
            if x0 <= nx <= x1 and y0 <= ny <= y1:
                if ny < (y0 + y1) * 0.5:
                    y0 = min(y0, ny - 8.0)
                else:
                    y1 = max(y1, ny + 8.0)

        x0 = float(np.clip(x0, 0, w - 1))
        y0 = float(np.clip(y0, 0, h - 1))
        x1 = float(np.clip(x1, 0, w - 1))
        y1 = float(np.clip(y1, 0, h - 1))
        if x1 <= x0:
            x1 = min(float(w - 1), x0 + 1.0)
        if y1 <= y0:
            y1 = min(float(h - 1), y0 + 1.0)

        return np.asarray([x0, y0, x1, y1], dtype=np.float32)

    def _dense_prompt_from_clicks(self, h, w, positive_points, negative_points, n_pts=64):
        """Create dense layer-like prompts from sparse clicks for better thin-layer segmentation."""
        if len(positive_points) == 0:
            return np.zeros((0, 2), dtype=np.float32), np.zeros((0,), dtype=np.int32)

        pos = np.asarray(positive_points, dtype=np.float32)
        order = np.argsort(pos[:, 0])
        pos = pos[order]

        if len(pos) == 1:
            x_grid = np.linspace(0, w - 1, n_pts, dtype=np.float32)
            y_grid = np.full((n_pts,), float(pos[0, 1]), dtype=np.float32)
        else:
            x_grid = np.linspace(float(pos[:, 0].min()), float(pos[:, 0].max()), n_pts, dtype=np.float32)
            uniq_x, uniq_idx = np.unique(pos[:, 0].astype(np.int32), return_index=True)
            uniq_y = pos[:, 1][uniq_idx]
            if len(uniq_x) == 1:
                y_grid = np.full((n_pts,), float(uniq_y[0]), dtype=np.float32)
            else:
                y_grid = np.interp(x_grid, uniq_x.astype(np.float32), uniq_y.astype(np.float32))

        dense_pos = np.stack([
            np.clip(x_grid, 0, w - 1),
            np.clip(y_grid, 0, h - 1),
        ], axis=1).astype(np.float32)

        dense_points = [dense_pos]
        dense_labels = [np.ones((dense_pos.shape[0],), dtype=np.int32)]

        if len(negative_points) > 0:
            neg = np.asarray(negative_points, dtype=np.float32)
            dense_points.append(np.clip(neg, [0.0, 0.0], [w - 1.0, h - 1.0]).astype(np.float32))
            dense_labels.append(np.zeros((neg.shape[0],), dtype=np.int32))
        else:
            # No explicit negatives: add weak synthetic negatives above and below the layer.
            off = float(max(4, int(0.03 * h)))
            sub = dense_pos[::2]
            neg_up = np.stack([sub[:, 0], np.clip(sub[:, 1] - off, 0, h - 1)], axis=1).astype(np.float32)
            neg_dn = np.stack([sub[:, 0], np.clip(sub[:, 1] + off, 0, h - 1)], axis=1).astype(np.float32)
            dense_points.extend([neg_up, neg_dn])
            dense_labels.extend([
                np.zeros((neg_up.shape[0],), dtype=np.int32),
                np.zeros((neg_dn.shape[0],), dtype=np.int32),
            ])

        pts = np.concatenate(dense_points, axis=0)
        labs = np.concatenate(dense_labels, axis=0)
        return pts.astype(np.float32), labs.astype(np.int32)

    def _build_prompt_variants(self, h, w):
        """Build multiple prompt variants and let scoring select the best output."""
        base_pts, base_labs = [], []
        for x, y in self.positive_points:
            base_pts.append([x, y])
            base_labs.append(1)
        for x, y in self.negative_points:
            base_pts.append([x, y])
            base_labs.append(0)

        base_pts = np.asarray(base_pts, dtype=np.float32)
        base_labs = np.asarray(base_labs, dtype=np.int32)

        box = self._auto_box_from_points(h, w, self.positive_points, self.negative_points)
        dense_pts, dense_labs = self._dense_prompt_from_clicks(
            h, w, self.positive_points, self.negative_points, n_pts=72
        )

        variants = [
            {
                "name": "clicks_multimask",
                "point_coords": base_pts,
                "point_labels": base_labs,
                "box": None,
                "multimask_output": True,
            }
        ]

        if box is not None:
            variants.append(
                {
                    "name": "clicks_plus_box",
                    "point_coords": base_pts,
                    "point_labels": base_labs,
                    "box": box,
                    "multimask_output": True,
                }
            )

        if dense_pts.shape[0] > 0:
            variants.append(
                {
                    "name": "dense_layer_prompt",
                    "point_coords": dense_pts,
                    "point_labels": dense_labs,
                    "box": box,
                    "multimask_output": True,
                }
            )

        return variants

    def _band_fallback_from_click(self, prob_map, positive_points, negative_points):
        """Fallback: search a horizontal band around clicks for a connected layer-like region."""
        if len(positive_points) == 0:
            return np.zeros_like(prob_map, dtype=np.uint8)

        H, W = prob_map.shape
        band_half = max(12, int(0.12 * H))
        best = np.zeros((H, W), dtype=np.uint8)

        for x, y in positive_points:
            py = int(np.clip(round(y), 0, H - 1))
            y0 = max(0, py - band_half)
            y1 = min(H, py + band_half + 1)

            band = np.zeros((H, W), dtype=np.uint8)
            band[y0:y1, :] = 1

            for thr in (0.08, 0.05, 0.03, 0.02, 0.01):
                candidate = ((prob_map >= thr).astype(np.uint8) * band).astype(np.uint8)
                candidate = self._extract_positive_component(
                    candidate, [(x, y)], prob_map=prob_map
                )
                if candidate.sum() == 0:
                    continue
                if self._hits_negative_point(candidate, negative_points):
                    continue
                if candidate.sum() > best.sum():
                    best = candidate

        return best

    def _best_binary_from_prob(self, prob_map, positive_points, negative_points):
        """Build a robust binary mask from a probability map using adaptive thresholds."""
        H, W = prob_map.shape
        min_area = max(25, int(0.0005 * H * W))
        max_area = int(0.30 * H * W)

        best_non_empty = np.zeros((H, W), dtype=np.uint8)

        # Start strict, then relax if needed.
        thresholds = (0.60, 0.50, 0.40, 0.30, 0.22, 0.16, 0.12, 0.10, 0.08, 0.06, 0.04, 0.03)
        for thr in thresholds:
            candidate = (prob_map > thr).astype(np.uint8)
            candidate = self._extract_positive_component(
                candidate, positive_points, prob_map=prob_map
            )
            candidate = self._enforce_thin_layer_geometry(
                candidate, prob_map, positive_points, negative_points
            )
            if candidate.sum() > best_non_empty.sum():
                best_non_empty = candidate
            if (
                candidate.sum() >= min_area
                and candidate.sum() <= max_area
                and not self._hits_negative_point(candidate, negative_points)
            ):
                return candidate

        # Click-seeded region growing from positive points.
        for x, y in positive_points:
            px = int(np.clip(round(x), 0, W - 1))
            py = int(np.clip(round(y), 0, H - 1))
            p_seed = float(prob_map[py, px])
            seed_thresholds = (
                max(0.35, p_seed * 0.9),
                max(0.20, p_seed * 0.7),
                max(0.10, p_seed * 0.5),
                0.05,
                0.03,
                0.02,
            )
            for thr in seed_thresholds:
                candidate = self._grow_region_from_seed(prob_map, px, py, thr)
                candidate = self._enforce_thin_layer_geometry(
                    candidate, prob_map, positive_points, negative_points
                )
                if candidate.sum() == 0:
                    continue
                if candidate.sum() > best_non_empty.sum():
                    best_non_empty = candidate
                if (
                    candidate.sum() >= min_area
                    and candidate.sum() <= max_area
                    and not self._hits_negative_point(candidate, negative_points)
                ):
                    return candidate

        # If logits are weak, build a tiny high-confidence region and anchor it to clicks.
        hi = np.percentile(prob_map, 99.5)
        lo = np.percentile(prob_map, 99.0)
        for thr in (hi, lo, float(prob_map.max() * 0.9), float(prob_map.max() * 0.8)):
            candidate = (prob_map >= thr).astype(np.uint8)
            candidate = self._extract_positive_component(
                candidate, positive_points, prob_map=prob_map
            )
            candidate = self._enforce_thin_layer_geometry(
                candidate, prob_map, positive_points, negative_points
            )
            if candidate.sum() > best_non_empty.sum():
                best_non_empty = candidate
            if (
                candidate.sum() >= min_area
                and candidate.sum() <= max_area
                and not self._hits_negative_point(candidate, negative_points)
            ):
                return candidate

        # Layer-style fallback: use a horizontal band around clicks.
        band_candidate = self._band_fallback_from_click(
            prob_map, positive_points, negative_points
        )
        band_candidate = self._enforce_thin_layer_geometry(
            band_candidate, prob_map, positive_points, negative_points
        )
        if band_candidate.sum() >= min_area and band_candidate.sum() <= max_area:
            return band_candidate
        if band_candidate.sum() > best_non_empty.sum():
            best_non_empty = band_candidate

        best_non_empty = self._recover_undersegmented_layer(
            best_non_empty, prob_map, positive_points, negative_points
        )
        if best_non_empty.sum() > 0:
            return best_non_empty

        # Last resort: mark positive clicks so users always get visible feedback.
        fallback = np.zeros_like(prob_map, dtype=np.uint8)
        H, W = fallback.shape
        for x, y in positive_points:
            px = int(np.clip(round(x), 0, W - 1))
            py = int(np.clip(round(y), 0, H - 1))
            fallback[max(0, py - 1):min(H, py + 2), max(0, px - 1):min(W, px + 2)] = 1
        if fallback.sum() > 0:
            return fallback

        return np.zeros_like(prob_map, dtype=np.uint8)

    def _score_candidate_mask(self, mask, iou_score, positive_points, negative_points):
        """Score a candidate using prompt consistency and compactness."""
        if mask.sum() == 0:
            return -1e9

        H, W = mask.shape

        def sample_points(points):
            vals = []
            for x, y in points:
                px = int(np.clip(round(x), 0, W - 1))
                py = int(np.clip(round(y), 0, H - 1))
                vals.append(mask[py, px])
            return np.mean(vals) if len(vals) > 0 else 0.0

        pos_hit = sample_points(positive_points) if len(positive_points) > 0 else 0.0
        neg_hit = sample_points(negative_points) if len(negative_points) > 0 else 0.0
        neg_clear = 1.0 - neg_hit

        area_ratio = float(mask.mean())
        area_penalty = max(0.0, area_ratio - 0.35) * 2.0

        return float(iou_score) + 1.5 * pos_hit + 1.0 * neg_clear - area_penalty

    def _run_segmentation(self):
        """Run predictor with current click prompts and select best mask."""
        if not self.positive_points and not self.negative_points:
            print("⚠  No points — left-click to add foreground, "
                  "right-click to add background.")
            return

        if self.image_embed is None:
            self._encode_image(self.current_idx)

        img = self.images[self.current_idx].astype(np.float32)
        h, w = img.shape

        variants = self._build_prompt_variants(h, w)

        best_idx = 0
        best_variant_name = ""
        best_score = -1e9
        best_mask = None
        best_prob = None
        best_iou_pred = 0.0

        for variant in variants:
            masks, iou_scores, logits = self.predictor.predict(
                point_coords=variant["point_coords"],
                point_labels=variant["point_labels"],
                box=variant["box"],
                multimask_output=variant["multimask_output"],
                return_logits=True,
                normalize_coords=False,
            )

            probs_low = 1.0 / (1.0 + np.exp(-np.clip(logits, -32.0, 32.0)))
            probs_t = torch.from_numpy(probs_low).unsqueeze(1).float()  # (K, 1, 256, 256)
            probs = F.interpolate(
                probs_t,
                size=(h, w),
                mode="bilinear",
                align_corners=False,
            ).squeeze(1).cpu().numpy()

            for k in range(probs.shape[0]):
                base_candidate = self._best_binary_from_prob(
                    probs[k], self.positive_points, self.negative_points
                )
                # Intersect with predictor mask only when it does not collapse too much.
                predictor_mask = masks[k].astype(np.uint8)
                intersected = (
                    base_candidate.astype(np.uint8) * predictor_mask
                ).astype(np.uint8)
                if intersected.sum() >= max(25, int(0.15 * max(1, base_candidate.sum()))):
                    working_candidate = intersected
                else:
                    working_candidate = base_candidate

                refined_candidate = self._refine_layer_mask(
                    working_candidate,
                    probs[k],
                    self.positive_points,
                    self.negative_points,
                    img,
                )
                refined_candidate = self._enforce_prompt_hard_constraints(
                    refined_candidate,
                    probs[k],
                    self.positive_points,
                    self.negative_points,
                )

                # Anti-collapse fallback: never keep a tiny mask if base candidate is larger.
                min_area = max(25, int(0.0005 * h * w))
                if refined_candidate.sum() < min_area:
                    fallback_candidate = self._restrict_to_positive_band(
                        base_candidate, self.positive_points
                    )
                    fallback_candidate = self._suppress_negative_neighborhood(
                        fallback_candidate, self.negative_points, radius=3
                    )
                    fallback_candidate = self._extract_positive_component(
                        fallback_candidate,
                        self.positive_points,
                        prob_map=probs[k],
                    )
                    if fallback_candidate.sum() > refined_candidate.sum():
                        candidate = fallback_candidate
                    else:
                        candidate = refined_candidate
                else:
                    candidate = refined_candidate

                candidate = self._enforce_prompt_hard_constraints(
                    candidate,
                    probs[k],
                    self.positive_points,
                    self.negative_points,
                )
                candidate = self._enforce_thin_layer_geometry(
                    candidate,
                    probs[k],
                    self.positive_points,
                    self.negative_points,
                )
                candidate = self._recover_undersegmented_layer(
                    candidate,
                    probs[k],
                    self.positive_points,
                    self.negative_points,
                )
                candidate = self._suppress_negative_neighborhood(
                    candidate,
                    self.negative_points,
                    radius=self.negative_guard_radius,
                )
                candidate = self._smooth_binary_mask(candidate)
                candidate = self._boost_positive_regions(
                    candidate,
                    probs[k],
                    self.positive_points,
                    self.negative_points,
                )
                candidate = self._suppress_negative_neighborhood(
                    candidate,
                    self.negative_points,
                    radius=self.negative_guard_radius + 2,
                )
                candidate = self._force_positive_anchors(
                    candidate,
                    probs[k],
                    self.positive_points,
                    self.negative_points,
                )
                candidate = self._extract_positive_component(
                    candidate,
                    self.positive_points,
                    prob_map=probs[k],
                )

                pos_hit = 0.0
                pos_cover = 0.0
                neg_hit = 0.0
                if self.positive_points:
                    pos_hit = float(np.mean([
                        self._point_is_inside_mask(candidate, x, y)
                        for x, y in self.positive_points
                    ]))
                    pos_cover = self._positive_coverage_ratio(
                        candidate,
                        self.positive_points,
                        radius=self.positive_anchor_radius,
                    )
                if self.negative_points:
                    neg_hit = self._negative_overlap_ratio(
                        candidate,
                        self.negative_points,
                        radius=max(2, self.negative_guard_radius),
                    )

                area_ratio = float(candidate.mean())
                area_penalty = max(0.0, area_ratio - 0.28) * 2.5
                score = (
                    float(iou_scores[k])
                    + 3.0 * pos_hit
                    + 7.0 * pos_cover
                    - 110.0 * neg_hit
                    - area_penalty
                )
                if score > best_score:
                    best_score = score
                    best_idx = int(k)
                    best_mask = candidate.copy()
                    best_prob = probs[k]
                    best_iou_pred = float(iou_scores[k])
                    best_variant_name = variant["name"]

        if best_mask is None:
            best_mask = np.zeros((h, w), dtype=np.uint8)
            best_prob = np.zeros((h, w), dtype=np.float32)

        self.current_mask = best_mask.astype(np.float32)
        self.iou_score = best_iou_pred

        print(
            "Debug | "
            f"max_prob={best_prob.max():.4f} "
            f"mean_prob={best_prob.mean():.4f} "
            f"mask_area={int(self.current_mask.sum())} "
            f"pos_points={len(self.positive_points)} "
            f"variant={best_variant_name} "
            f"k={best_idx}"
        )

        print(f"✓ Segmentation done  |  IoU prediction: {self.iou_score:.3f}")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_click(self, event):
        if event.inaxes != self.ax or event.xdata is None:
            return
        x, y = event.xdata, event.ydata
        if event.button == 1:          # left = positive
            self.positive_points.append((x, y))
        elif event.button == 3:        # right = negative
            self.negative_points.append((x, y))
        else:
            return
        self._update_display()

    def _on_key(self, event):
        key = event.key
        if key in ("enter", "return", "\n"):
            self._run_segmentation()
        elif key == "c":
            self.positive_points.clear()
            self.negative_points.clear()
            self.current_mask = None
            self.iou_score = None
            print("Cleared points and mask.")
        elif key == "n":
            self.current_idx = (self.current_idx + 1) % len(self.images)
            self._reset_state()
            self._encode_image(self.current_idx)
            print(f"→ Image {self.current_idx}")
        elif key == "p":
            self.current_idx = (self.current_idx - 1) % len(self.images)
            self._reset_state()
            self._encode_image(self.current_idx)
            print(f"→ Image {self.current_idx}")
        elif key == "s":
            self._save_mask()
        elif key in ("q", "escape"):
            plt.close(self.fig)
            return
        else:
            return
        self._update_display()

    def _reset_state(self):
        self.positive_points.clear()
        self.negative_points.clear()
        self.current_mask = None
        self.iou_score = None
        self.image_embed = None
        self.high_res_feats = None

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------
    def _save_mask(self):
        if self.current_mask is not None:
            path = os.path.join(
                self.output_dir, f"mask_{self.current_idx:04d}.npy"
            )
            np.save(path, self.current_mask)
            print(f"💾 Mask saved → {path}")
        else:
            print("⚠  No mask to save. Press Enter to segment first.")

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------
    def _update_display(self):
        self.ax.clear()
        img = self.images[self.current_idx]
        self.ax.imshow(img, cmap="gray")

        # Overlay segmentation mask
        if self.current_mask is not None:
            rgba = np.zeros((*self.current_mask.shape, 4), dtype=np.float32)
            rgba[self.current_mask > 0] = [0.0, 1.0, 0.0, 0.4]  # green
            self.ax.imshow(rgba)

        # Draw points
        for x, y in self.positive_points:
            self.ax.plot(
                x, y, "o", color="lime", markersize=10,
                markeredgecolor="white", markeredgewidth=1.5,
            )
        for x, y in self.negative_points:
            self.ax.plot(
                x, y, "o", color="red", markersize=10,
                markeredgecolor="white", markeredgewidth=1.5,
            )

        iou_str = f"  IoU={self.iou_score:.3f}" if self.iou_score else ""
        title = (
            f"Image {self.current_idx}/{len(self.images) - 1}{iou_str}  |  "
            "● green=positive  ● red=negative  |  "
            "Enter=segment  C=clear  N=next  P=prev  S=save  Q=quit"
        )
        self.ax.set_title(title, fontsize=9)
        self.ax.axis("off")
        self.fig.canvas.draw()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self):
        self._encode_image(self.current_idx)
        self._update_display()
        plt.tight_layout()
        plt.show()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Interactive OCT annotation tool with fine-tuned MedSAM2"
    )
    parser.add_argument(
        "--model", type=str,
        default="checkpoints/best_medsam2_oct_finetuned.pth",
        help="Path to fine-tuned model checkpoint",
    )
    parser.add_argument(
        "--sam_config", type=str, default="sam2_hiera_t",
        help="SAM2 hydra config name",
    )
    parser.add_argument(
        "--data_dir", type=str, default="dataset",
        help="Path to dataset directory",
    )
    parser.add_argument(
        "--dicom_file", type=str, default="images.dcm",
        help="Name of the OCT DICOM file in data_dir",
    )
    parser.add_argument(
        "--image_index", type=int, default=0,
        help="Starting image index",
    )
    parser.add_argument(
        "--gpu_device", type=int, default=0,
        help="GPU device index",
    )
    parser.add_argument(
        "--output_dir", type=str, default="annotations",
        help="Directory to save annotation masks",
    )
    parser.add_argument(
        "--smoothing_strength", type=str, default="medium",
        choices=["light", "medium", "strong"],
        help="Mask smoothing strength",
    )
    parser.add_argument(
        "--negative_guard_radius", type=int, default=6,
        help="Exclusion radius around negative points",
    )
    parser.add_argument(
        "--positive_boost_strength", type=str, default="strong",
        choices=["light", "medium", "strong"],
        help="Positive-region recovery strength",
    )
    parser.add_argument(
        "--positive_anchor_radius", type=int, default=4,
        help="Neighborhood radius that must be covered around each positive point",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(message)s"
    )
    logger = logging.getLogger(__name__)

    device = torch.device(
        f"cuda:{args.gpu_device}" if torch.cuda.is_available() else "cpu"
    )
    logger.info(f"Device: {device}")

    # --- build model ---
    logger.info("Building model ...")
    cfg = compose(config_name=args.sam_config)
    OmegaConf.resolve(cfg)
    model = instantiate(cfg.model, _recursive_=True)

    # --- load fine-tuned weights ---
    logger.info(f"Loading checkpoint: {args.model}")
    ckpt = torch.load(args.model, map_location="cpu", weights_only=False)
    state = ckpt["model"] if "model" in ckpt else ckpt
    model.load_state_dict(state, strict=False)
    model = model.to(device)
    model.eval()
    logger.info("Model ready.")

    # --- load images from DICOM ---
    dicom_path = os.path.join(args.data_dir, args.dicom_file)
    if not os.path.exists(dicom_path):
        raise FileNotFoundError(f"DICOM file not found: {dicom_path}")

    logger.info(f"Loading OCT DICOM: {dicom_path}")
    images = load_oct_dicom_images(dicom_path)
    logger.info(f"Loaded DICOM frames: shape={images.shape} dtype={images.dtype}")

    # --- run annotator ---
    annotator = OCTAnnotator(
        model,
        images,
        device=device,
        output_dir=args.output_dir,
        smoothing_strength=args.smoothing_strength,
        negative_guard_radius=args.negative_guard_radius,
        positive_boost_strength=args.positive_boost_strength,
        positive_anchor_radius=args.positive_anchor_radius,
    )
    annotator.current_idx = args.image_index
    annotator.run()


if __name__ == "__main__":
    main()
