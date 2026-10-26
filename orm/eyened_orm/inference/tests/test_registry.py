"""Contract every registered model must meet."""

from __future__ import annotations

import pytest

from eyened_orm.inference.model_versions import package_distribution_version
from eyened_orm.inference.outputs import AttributeOutput, SegmentationOutput
from eyened_orm.inference.registry import MODELS, ModelSpec, get_spec


def _load(spec: ModelSpec):
    try:
        return spec.load()
    except ImportError as exc:
        pytest.skip(f"{spec.slug} needs an optional dependency: {exc}")


@pytest.mark.parametrize("slug", list(MODELS))
def test_spec_loads_a_pipeline_with_an_output(slug):
    spec = MODELS[slug]
    cls = _load(spec)

    assert spec.slug == slug
    assert spec.modalities
    assert isinstance(cls.output, (AttributeOutput, SegmentationOutput))


@pytest.mark.parametrize("slug", list(MODELS))
def test_inputs_are_produced_by_an_earlier_model(slug):
    slugs = list(MODELS)
    earlier = {
        (out.model_name, out.attribute_name)
        for out in (_load(MODELS[s]).output for s in slugs[: slugs.index(slug)])
        if isinstance(out, AttributeOutput)
    }
    for upscale in (False, True):
        for spec in _load(MODELS[slug])(upscale=upscale).inputs:
            assert (spec.model_name, spec.attribute_name) in earlier, spec


def test_cfi_roi_needs_no_torch_and_is_versioned_by_fundusprep():
    cls = _load(MODELS["cfi-roi"])

    assert cls.needs_torch is False
    assert cls.output.version == package_distribution_version("retinalysis-fundusprep")


def test_unknown_slug_lists_the_choices():
    with pytest.raises(ValueError, match="cfi-roi"):
        get_spec("nope")


@pytest.mark.parametrize(("images", "timeout"), [(0, 600), (3, 1800), (1000, 86400)])
def test_job_timeout_scales_with_images_within_bounds(images, timeout):
    spec = ModelSpec("x", "m:C", (), seconds_per_image=600)
    assert spec.job_timeout(images) == timeout
    assert ModelSpec("y", "m:C", ()).job_timeout(images) is None
