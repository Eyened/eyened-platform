from collections import defaultdict, deque
from pathlib import Path

from eyened_orm import Creator, FormAnnotation, FormSchema, ImageInstance
from rtnls_registration import Registration


def get_or_create_schema(session, schema_name):
    schema = FormSchema.by_name(session, schema_name)
    if schema is None:
        import json

        current_dir = Path(__file__).parent
        schema_path = current_dir / "registration_schema.json"

        with open(schema_path, "r") as f:
            schema_dict = json.load(f)

        schema = FormSchema(SchemaName=schema_name, Schema=schema_dict)
        print(f"Created schema for registration set using name '{schema_name}'")
        session.add(schema)
        session.commit()
    return schema


def get_or_create_creator(session, creator_name):
    creator = Creator.by_name(session, creator_name)
    if creator is None:
        creator = Creator(CreatorName=creator_name, IsHuman=True)
        session.add(creator)
        session.commit()
        print(f"Created creator for registration set using name '{creator_name}'")
    return creator


def get_or_create_FormAnnotation(session, patient, schema, creator):
    """
    Get or create a form annotation for a patient.
    """
    formAnnotation = FormAnnotation.where(
        session,
        (FormAnnotation.FormSchemaID == schema.FormSchemaID)
        & (FormAnnotation.CreatorID == creator.CreatorID)
        & (FormAnnotation.PatientID == patient.PatientID),
    )
    if formAnnotation:
        if len(formAnnotation) > 1:
            print(
                f"Found multiple form annotations for patient {patient.PatientID}, using the first one ({formAnnotation[0].FormAnnotationID})"
            )
        return formAnnotation[0]

    formAnnotation = FormAnnotation()
    formAnnotation.Creator = creator
    formAnnotation.FormSchema = schema
    formAnnotation.Patient = patient
    formAnnotation.FormData = []

    session.add(formAnnotation)
    session.commit()
    return formAnnotation


def get_processed_edges(formAnnotation):
    if formAnnotation.FormData:
        processed = {(e["image1"], e["image2"]) for e in formAnnotation.FormData}
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
    if image.NrOfFrames > 1:
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


def run_registration_patient(patient, formAnnotation):
    print(
        f"Running registration for patient {patient.PatientID} {patient.PatientIdentifier}"
    )
    enface_images = patient.get_images(
        where=ImageInstance.Modality.in_(
            ["ColorFundus", "InfraredReflectance", "Autofluorescence"]
        )
    )
    print(f"Found {len(enface_images)} enface images")
    graph = get_processed_edges(formAnnotation)
    print(f"Found {len(graph)} processed pairs")

    all_transforms = [*formAnnotation.FormData] if formAnnotation.FormData else []
    for eye in "RL":

        eye_images = [i for i in enface_images if i.Laterality.name == eye]

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
            registration.M0 = register_f1.M0
            registration.kp0_005 = register_f1.kp0_005
            registration.des0_005 = register_f1.des0_005
            registration.kp0_01 = register_f1.kp0_01
            registration.des0_01 = register_f1.des0_01

            registration.M1 = register_f2.M0
            registration.kp1_005 = register_f2.kp0_005
            registration.des1_005 = register_f2.des0_005
            registration.kp1_01 = register_f2.kp0_01
            registration.des1_01 = register_f2.des0_01
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


def run_patient(session, patient, schema, creator, replace):
    formAnnotation = get_or_create_FormAnnotation(session, patient, schema, creator)
    if replace:
        formAnnotation.FormData = []

    all_transforms = run_registration_patient(patient, formAnnotation)
    formAnnotation.FormData = all_transforms

    session.add(formAnnotation)
    session.commit()
