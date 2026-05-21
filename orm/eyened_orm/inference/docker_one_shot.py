"""CLI for one-shot inference inside worker containers (no DB)."""

from __future__ import annotations

import argparse

import numpy as np


def _cmd_layer(input_path: str, output_path: str) -> None:
    from eyened_orm.inference.layer_segmentation import predict_volume

    volume = np.load(input_path)
    layers = predict_volume(volume)
    np.save(output_path, layers)


def _cmd_cfi_amd(input_path: str, output_path: str) -> None:
    from eyened_orm.inference.cfi_amd_segmentation import predict_image

    result = predict_image(input_path)
    np.savez(output_path, **result)


def main() -> None:
    parser = argparse.ArgumentParser(description="One-shot model inference (no ORM/DB).")
    sub = parser.add_subparsers(dest="model", required=True)

    for name in ("layer", "cfi-amd"):
        p = sub.add_parser(name)
        p.add_argument("--input", required=True)
        p.add_argument("--output", required=True)

    args = parser.parse_args()
    if args.model == "layer":
        _cmd_layer(args.input, args.output)
    else:
        _cmd_cfi_amd(args.input, args.output)


if __name__ == "__main__":
    main()
