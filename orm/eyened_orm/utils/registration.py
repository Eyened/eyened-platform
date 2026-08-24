from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

import numpy as np
from eyened_orm import AttributeValue, ImageInstance
from rtnls_registration import Registration
from rtnls_registration.transformation import (
    CompositeTransform,
    Polynomial2DTransform,
    ProjectiveTransform,
    Transform,
)
from sklearn.linear_model import LinearRegression


def transform_from_dict(d: dict[str, Any]) -> Transform:
    """Reconstruct an rtnls_registration transform from JSON (e.g. ``AttributeValue.ValueJSON`` edge)."""
    ttype = d["type"]
    if ttype == "CompositeTransform":
        return CompositeTransform([transform_from_dict(t) for t in d["transforms"]])
    if ttype == "ProjectiveTransform":
        return ProjectiveTransform(np.array(d["Matrix"], dtype=float).reshape(3, 3))
    if ttype == "Polynomial2DTransform":

        def _model_from_coefs(coefs: list[float]) -> LinearRegression:
            model = LinearRegression()
            model.intercept_ = coefs[0]
            model.coef_ = np.array(coefs[1:], dtype=float)
            return model

        return Polynomial2DTransform(
            _model_from_coefs(d["dx"]),
            _model_from_coefs(d["dy"]),
            degree=d["degree"],
        )
    raise ValueError(f"Unknown transform type: {ttype!r}")


def registration_image_key(image: ImageInstance) -> str:
    """Public image identifier stored in registration JSON (matches viewer ``image_id``)."""
    return image.PublicID


def collect_legacy_instance_ids(transforms: list[dict[str, Any]]) -> set[int]:
    ids: set[int] = set()
    for edge in transforms:
        for key in ("image1", "image2"):
            val = edge.get(key)
            if isinstance(val, int):
                ids.add(val)
            elif isinstance(val, str) and val.isdigit():
                ids.add(int(val))
    return ids


def build_id_to_public(session, instance_ids: set[int]) -> dict[int, str]:
    if not instance_ids:
        return {}
    images = ImageInstance.by_columns(session, ImageInstanceID=instance_ids)
    return {im.ImageInstanceID: im.PublicID for im in images}


def normalize_registration_key(
    key: str | int, id_to_public: dict[int, str]
) -> str:
    if isinstance(key, str) and not key.isdigit():
        return key
    int_id = int(key)
    return id_to_public.get(int_id, str(int_id))


def normalize_registration_transforms(
    transforms: list[dict[str, Any]], id_to_public: dict[int, str]
) -> list[dict[str, Any]]:
    return [
        {
            **edge,
            "image1": normalize_registration_key(edge["image1"], id_to_public),
            "image2": normalize_registration_key(edge["image2"], id_to_public),
        }
        for edge in transforms
    ]


def graph_from_transforms(
    transforms: list[dict[str, Any]], id_to_public: dict[int, str] | None = None
):
    id_to_public = id_to_public or {}
    graph = defaultdict(set)
    for edge in transforms:
        img1 = normalize_registration_key(edge["image1"], id_to_public)
        img2 = normalize_registration_key(edge["image2"], id_to_public)
        graph[img1].add(img2)
        graph[img2].add(img1)
    return graph


def get_processed_edges(
    attribute_value: AttributeValue, id_to_public: dict[int, str] | None = None
):
    id_to_public = id_to_public or {}
    transforms = attribute_value.ValueJSON or []
    return graph_from_transforms(transforms, id_to_public)


def collect_registration_seed_transforms(
    session, patient, attribute_id: int, *, replace: bool
) -> list[dict[str, Any]]:
    """All stored registration edges for this patient/attribute (any model version)."""
    if replace:
        return []

    attribute_values = AttributeValue.by_columns(
        session,
        PatientID=patient.PatientID,
        AttributeID=attribute_id,
    )
    seed: list[dict[str, Any]] = []
    for av in attribute_values:
        if av.ValueJSON:
            seed.extend(av.ValueJSON)
    return seed


def are_connected(image_id1, image_id2, graph):
    """
    Check if two images are connected through any path in the processed graph.
    """
    if image_id1 == image_id2:
        return True

    if image_id1 not in graph or image_id2 not in graph:
        return False

    queue = deque([image_id1])
    visited = {image_id1}

    while queue:
        current = queue.popleft()
        if current == image_id2:
            return True

        for neighbor in graph[current]:
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)

    return False


def get_etdrs_field(image):
    if image.ETDRSField:
        if image.ETDRSField.name == "F1":
            return "F1"
        if image.ETDRSField.name == "F2":
            return "F2"

    if image.CFKeypoints and image.CFROI:
        fx, _ = image.CFKeypoints["fovea_xy"]
        cx, _ = image.CFROI["center"]
        r = image.CFROI["radius"]
        d = abs(cx - fx) / r
        return "F2" if d < 0.5 else "F1"

    if image.Modality and image.Modality.name in (
        "InfraredReflectance",
        "Autofluorescence",
    ):
        return "F2"

    return None


def sort_images(images):
    groups = {"F1": [], "F2": [], "Other": []}
    for image in images:
        field = get_etdrs_field(image)
        if field in groups:
            groups[field].append(image)
    return groups


def get_pixel_array(image):
    if image.NrOfFrames and image.NrOfFrames > 1:
        return image.pixel_array[0]
    else:
        return image.pixel_array


def run_registration(image_set, graph, new_transforms):
    if not image_set:
        return None, None

    reference = max(image_set, key=lambda i: i.CFQuality if i.CFQuality else 0)
    ref_key = registration_image_key(reference)

    registrator = Registration()
    registrator.set_reference(get_pixel_array(reference))

    for i in image_set:
        i_key = registration_image_key(i)
        if are_connected(ref_key, i_key, graph):
            continue

        registrator.set_target(get_pixel_array(i))
        try:
            print(
                f"Running registration for {ref_key} -> {i_key} "
            )
            transform = registrator.run()
            graph[ref_key].add(i_key)
            graph[i_key].add(ref_key)
            new_transforms.append(
                {
                    "image1": ref_key,
                    "image2": i_key,
                    "transform": transform.to_dict(),
                }
            )
        except Exception as e:
            print(
                f"Error running registration for {ref_key}, {i_key}: {e}"
            )

    return registrator, reference


def run_registration_patient(
    patient,
    seed_transforms: list[dict[str, Any]],
    skip_ids=None,
    session=None,
):
    print(
        f"Running registration for patient {patient.PatientID} {patient.PatientIdentifier}"
    )

    modality_filter = ImageInstance.Modality.in_(
        ["ColorFundus", "InfraredReflectance", "Autofluorescence"]
    )

    if skip_ids:
        skip_filter = ~ImageInstance.ImageInstanceID.in_(skip_ids)
        where_clause = modality_filter & skip_filter
        print(f"Skipping {len(skip_ids)} imageInstanceIDs: {skip_ids}")
    else:
        where_clause = modality_filter

    enface_images = patient.get_images(where=where_clause)
    print(f"Found {len(enface_images)} enface images")

    id_to_public = {
        im.ImageInstanceID: im.PublicID for im in enface_images
    }
    if session is not None:
        legacy_ids = collect_legacy_instance_ids(seed_transforms)
        id_to_public.update(build_id_to_public(session, legacy_ids))

    seed_normalized = normalize_registration_transforms(seed_transforms, id_to_public)
    graph = graph_from_transforms(seed_normalized, id_to_public)
    print(f"Found {len(graph)} processed pairs in seed graph")

    new_transforms: list[dict[str, Any]] = []
    for eye in "RL":

        eye_images = [
            i for i in enface_images if i.Laterality and i.Laterality.name == eye
        ]

        sorted_images = sort_images(eye_images)

        register_f1 = None
        register_f2 = None
        if sorted_images["F1"]:
            print("Running registration for F1 images")
            register_f1, reference_f1 = run_registration(
                sorted_images["F1"], graph, new_transforms
            )

        if sorted_images["F2"]:
            print("Running registration for F2 images")
            register_f2, reference_f2 = run_registration(
                sorted_images["F2"], graph, new_transforms
            )

        if (
            register_f1
            and register_f2
            and reference_f1 is not None
            and reference_f2 is not None
        ):
            ref_f1 = registration_image_key(reference_f1)
            ref_f2 = registration_image_key(reference_f2)
            if not are_connected(ref_f1, ref_f2, graph):
                registration = Registration()
                registration.set_reference(get_pixel_array(reference_f1))
                registration.set_target(get_pixel_array(reference_f2))

                try:
                    transform = registration.run()
                    graph[ref_f1].add(ref_f2)
                    graph[ref_f2].add(ref_f1)
                    new_transforms.append(
                        {
                            "image1": ref_f1,
                            "image2": ref_f2,
                            "transform": transform.to_dict(),
                        }
                    )
                except Exception as e:
                    print(
                        f"Error running reference-to-reference registration "
                        f"for {ref_f1}, {ref_f2}: {e}"
                    )

    return normalize_registration_transforms(new_transforms, id_to_public)


def run_patient(session, patient, definition, model, replace, skip_ids=None):
    attribute_value = AttributeValue.get_or_create(
        session,
        match_by={
            "AttributeID": definition.AttributeID,
            "ModelID": model.ModelID,
            "PatientID": patient.PatientID,
        },
    )
    if replace:
        attribute_value.ValueJSON = []

    seed_transforms = collect_registration_seed_transforms(
        session,
        patient,
        definition.AttributeID,
        replace=replace,
    )
    new_transforms = run_registration_patient(
        patient, seed_transforms, skip_ids, session=session
    )

    if replace:
        attribute_value.ValueJSON = new_transforms
    else:
        existing = list(attribute_value.ValueJSON or [])
        existing.extend(new_transforms)
        attribute_value.ValueJSON = existing

    session.add(attribute_value)
    session.commit()
