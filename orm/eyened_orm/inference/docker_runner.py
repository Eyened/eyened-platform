"""Run one-shot inference in worker Docker images (weights baked in)."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Union

import numpy as np

from eyened_orm.inference.cfi_amd_segmentation import coerce_cfi_rgb_uint8
from eyened_orm.inference.layer_segmentation import load_layer_volume

PathLike = Union[str, Path]
LayerVolumeInput = Union[np.ndarray, PathLike]
CfiImageInput = Union[np.ndarray, PathLike]

_WORKER_COMPOSE = {
    "layer-segmentation": (
        "docker-compose.layersegmentation.yml",
        "worker-layersegmentation",
    ),
    "cfi-amd": ("docker-compose.cfi-amd.yml", "worker-cfi-amd"),
}

_LAYER_PREDICT_PY = (
    "import numpy as np; "
    "from eyened_orm.inference.layer_segmentation import predict_volume; "
    "v=np.load('/data/input.npy'); "
    "o=predict_volume(v); "
    "np.save('/data/output.npy', o)"
)

_CFI_AMD_PREDICT_PY = (
    "from eyened_orm.inference.cfi_amd_segmentation import predict_image; "
    "import numpy as np; "
    "r=predict_image('/data/input.png'); "
    "np.savez('/data/output.npz', **{k: np.asarray(v) for k, v in r.items()})"
)


def _log(msg: str) -> None:
    print(f"[docker-runner] {msg}", flush=True)


def _preflight_cuda_image(image: str, compose_file: str) -> None:
    """Quick CUDA smoke test so stale images fail before a long nnU-Net run."""
    probe = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--gpus",
            "all",
            image,
            "python",
            "-c",
            "import torch; v=torch.__version__; "
            "torch.zeros(1,device='cuda').add_(1); torch.cuda.synchronize(); "
            "print(v)",
        ],
        capture_output=True,
        text=True,
    )
    if probe.returncode == 0:
        return
    hint = (
        f"cd {_worker_dir()} && docker compose -f {compose_file} build"
    )
    detail = (probe.stderr or probe.stdout or "").strip()[:800]
    raise RuntimeError(
        f"Worker image {image!r} cannot run CUDA on this GPU "
        f"(likely stale PyTorch; Dockerfile expects 2.7+cu128). Rebuild:\n  {hint}"
        + (f"\n{detail}" if detail else "")
    )


def platform_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _worker_dir() -> Path:
    return Path(os.environ.get("EYENED_WORKER_DIR", platform_root() / "worker"))


def _image_for_service(compose_file: str, service: str) -> str:
    """Resolve built image ref (``docker compose images -q`` is often empty)."""
    result = subprocess.run(
        ["docker", "compose", "-f", compose_file, "config", "--images"],
        cwd=_worker_dir(),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Could not resolve Docker image for {service}:\n{result.stderr}"
        )
    for ref in reversed(result.stdout.splitlines()):
        ref = ref.strip()
        if not ref:
            continue
        probe = subprocess.run(
            ["docker", "image", "inspect", ref],
            capture_output=True,
        )
        if probe.returncode == 0:
            return ref
    raise RuntimeError(
        f"Image for {service} not found. Build it first:\n"
        f"  cd {_worker_dir()} && docker compose -f {compose_file} build"
    )


def _run_container(
    model: str,
    container_args: list[str],
    mounts: list[tuple[Path, Path, bool]],
    *,
    use_gpu: bool = True,
) -> None:
    """``docker run`` one-off; stream stdout/stderr to the notebook terminal."""
    compose_file, _service = _WORKER_COMPOSE[model]
    image = _image_for_service(compose_file, _service)
    orm_dir = platform_root() / "orm"
    use_gpu = use_gpu and os.environ.get("EYENED_INFERENCE_NO_GPU") != "1"

    cmd = [
        "docker",
        "run",
        "--rm",
        "-w",
        "/app",
        "-e",
        "PYTHONPATH=/app",
        "-e",
        "PYTHONUNBUFFERED=1",
        "-e",
        "NNUNET_RESULTS=/nnUNet_results",
        "-e",
        "nnUNet_results=/nnUNet_results",
        "-e",
        "nnUNet_raw=/nnUNet_results",
        "-e",
        "nnUNet_preprocessed=/nnUNet_results",
    ]
    if model == "cfi-amd":
        cmd.extend(["-e", "CFI_AMD_MODELS_DIR=/models/cfi-amd"])
    if use_gpu:
        cmd.extend(["--gpus", "all"])
    else:
        _log("GPU disabled (use_gpu=False or EYENED_INFERENCE_NO_GPU=1)")
    if orm_dir.is_dir():
        cmd.extend(["-v", f"{orm_dir.resolve()}:/app/orm"])
    for host, container, read_only in mounts:
        opt = ":ro" if read_only else ""
        cmd.extend(["-v", f"{host.resolve()}:{container}{opt}"])
    cmd.append(image)
    cmd.extend(container_args)

    if use_gpu:
        _preflight_cuda_image(image, compose_file)
    t0 = time.perf_counter()
    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise RuntimeError(
            f"Docker inference failed (exit {result.returncode}) after "
            f"{time.perf_counter() - t0:.1f}s — see messages above"
        )
    _log(f"{model} finished in {time.perf_counter() - t0:.1f}s")


def predict_layers_docker(
    volume: LayerVolumeInput, *, use_gpu: bool = True
) -> np.ndarray:
    """Run layer segmentation in the layer-segmentation worker image."""
    vol = load_layer_volume(volume)
    n = vol.shape[0] if vol.ndim == 3 else 1
    _log(f"layer-segmentation: shape={vol.shape} ({n} B-scans), gpu={use_gpu}")
    with tempfile.TemporaryDirectory(prefix="layerseg_") as td:
        td_path = Path(td)
        inp = td_path / "input.npy"
        out = td_path / "output.npy"
        np.save(inp, vol)
        _run_container(
            "layer-segmentation",
            ["python", "-u", "-c", _LAYER_PREDICT_PY],
            [(td_path, Path("/data"), False)],
            use_gpu=use_gpu,
        )
        return np.load(out)


def _write_cfi_input_png(image: CfiImageInput, dest: Path) -> None:
    if isinstance(image, np.ndarray):
        from PIL import Image

        Image.fromarray(coerce_cfi_rgb_uint8(image)).save(dest)
    else:
        shutil.copy2(Path(image), dest)


def predict_cfi_amd_docker(
    image: CfiImageInput,
    *,
    use_gpu: bool = True,
) -> dict[str, np.ndarray]:
    """Run CFI AMD in the cfi-amd worker image. RGB uint8 array or image file path."""
    shape = getattr(image, "shape", None)
    _log(f"cfi-amd: gpu={use_gpu}" + (f" shape={shape}" if shape is not None else ""))
    with tempfile.TemporaryDirectory(prefix="cfi_amd_") as td:
        td_path = Path(td)
        _write_cfi_input_png(image, td_path / "input.png")
        out = td_path / "output.npz"
        _run_container(
            "cfi-amd",
            ["python", "-u", "-c", _CFI_AMD_PREDICT_PY],
            [(td_path, Path("/data"), False)],
            use_gpu=use_gpu,
        )
        loaded = np.load(out)
        return {k: loaded[k] for k in loaded.files}


def predict_layers(
    volume: LayerVolumeInput,
    *,
    use_docker: bool | None = None,
    use_gpu: bool = True,
) -> np.ndarray:
    """Predict retinal layers. ``volume`` is uint8 ``(D, H, W)`` or a ``.npy`` path."""
    if use_docker is None:
        use_docker = os.environ.get("EYENED_PREDICT_USE_DOCKER", "1") == "1"
    if use_docker:
        return predict_layers_docker(volume, use_gpu=use_gpu)
    from eyened_orm.inference.layer_segmentation import predict_volume

    return predict_volume(volume)


def predict_cfi_amd(
    image: CfiImageInput,
    *,
    use_docker: bool | None = None,
    use_gpu: bool = True,
) -> dict[str, np.ndarray]:
    """Predict CFI AMD maps. RGB uint8 ``(H, W, 3)`` or an image file path."""
    if use_docker is None:
        use_docker = os.environ.get("EYENED_PREDICT_USE_DOCKER", "1") == "1"
    if use_docker:
        return predict_cfi_amd_docker(image, use_gpu=use_gpu)
    from eyened_orm.inference.cfi_amd_segmentation import predict_image

    return predict_image(image)
