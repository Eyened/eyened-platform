from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

import numpy as np
from eyened_orm import ImageInstance, AttributeValue
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


def get_processed_edges(attribute_value: AttributeValue):
    transforms = attribute_value.ValueJSON or []
    if transforms:
        processed = {(e["image1"], e["image2"]) for e in transforms}
    else:
        processed = set()

    # Build adjacency list from the processed edges (bidirectional)
    graph = defaultdict(set)
    for img1, img2 in processed:
        graph[img1].add(img2)
        graph[img2].add(img1)
    return graph


def are_connected(image_id1, image_id2, graph):
    """
    Check if two images are connected through any path in the processed graph.
    """
    if image_id1 == image_id2:
        return True

    # BFS to check connectivity
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
        # derive field from location of fovea relative to center of the image
        fx, _ = image.CFKeypoints["fovea_xy"]
        cx, _ = image.CFROI["center"]
        r = image.CFROI["radius"]
        d = abs(cx - fx) / r
        # F2 if fovea is closer to center than 0.5 of the radius, F1 otherwise
        return "F2" if d < 0.5 else "F1"

    if image.Modality and image.Modality.name in (
        "InfraredReflectance",
        "Autofluorescence",
    ):
        # assume that these are F2
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
        # Note: using only the first frame for registration
        return image.pixel_array[0]
    else:
        return image.pixel_array


def run_registration(image_set, graph, form_data):
    # Skip if image set is empty
    if not image_set:
        return None, None

    # best quality image as reference
    reference = max(image_set, key=lambda i: i.CFQuality if i.CFQuality else 0)

    registrator = Registration()
    registrator.set_reference(get_pixel_array(reference))

    for i in image_set:
        if are_connected(reference.ImageInstanceID, i.ImageInstanceID, graph):
            continue

        registrator.set_target(get_pixel_array(i))
        try:
            print(
                f"Running registration for {reference.ImageInstanceID} -> {i.ImageInstanceID}"
            )
            transform = registrator.run()
            graph[reference.ImageInstanceID].add(i.ImageInstanceID)
            graph[i.ImageInstanceID].add(reference.ImageInstanceID)
            form_data.append(
                {
                    "image1": reference.ImageInstanceID,
                    "image2": i.ImageInstanceID,
                    "transform": transform.to_dict(),
                }
            )
        except Exception as e:
            print(
                f"Error running registration for {reference.ImageInstanceID}, {i.ImageInstanceID}: {e}"
            )

    return registrator, reference


def run_registration_patient(patient, attribute_value: AttributeValue, skip_ids=None):
    print(
        f"Running registration for patient {patient.PatientID} {patient.PatientIdentifier}"
    )

    # Build the where clause to filter by modality and exclude skipped images
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
    graph = get_processed_edges(attribute_value)
    print(f"Found {len(graph)} processed pairs")

    all_transforms = list(attribute_value.ValueJSON or [])
    for eye in "RL":

        eye_images = [
            i for i in enface_images if i.Laterality and i.Laterality.name == eye
        ]

        # split images into F1 and F2
        sorted_images = sort_images(eye_images)

        register_f1 = None
        register_f2 = None
        if sorted_images["F1"]:
            print(f"Running registration for F1 images")
            register_f1, reference_f1 = run_registration(
                sorted_images["F1"], graph, all_transforms
            )

        if sorted_images["F2"]:
            print(f"Running registration for F2 images")
            register_f2, reference_f2 = run_registration(
                sorted_images["F2"], graph, all_transforms
            )

        if (
            register_f1
            and register_f2
            and not are_connected(
                reference_f1.ImageInstanceID, reference_f2.ImageInstanceID, graph
            )
        ):
            # register the two reference images
            registration = Registration()
            registration.set_reference(get_pixel_array(reference_f1))
            registration.set_target(get_pixel_array(reference_f2))

            try:
                transform = registration.run()
                graph[reference_f1.ImageInstanceID].add(reference_f2.ImageInstanceID)
                graph[reference_f2.ImageInstanceID].add(reference_f1.ImageInstanceID)
                all_transforms.append(
                    {
                        "image1": reference_f1.ImageInstanceID,
                        "image2": reference_f2.ImageInstanceID,
                        "transform": transform.to_dict(),
                    }
                )
            except Exception as e:
                print(
                    f"Error running reference-to-reference registration for {reference_f1.ImageInstanceID}, {reference_f2.ImageInstanceID}: {e}"
                )

    return all_transforms


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

    all_transforms = run_registration_patient(patient, attribute_value, skip_ids)
    attribute_value.ValueJSON = all_transforms

    session.add(attribute_value)
    session.commit()
