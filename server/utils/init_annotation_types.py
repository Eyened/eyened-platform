from eyened_orm import AnnotationType

def init_annotation_types(session):
    types = (
        'Segmentation 2D',
        'Segmentation OCT B-scan',
        'Segmentation OCT Enface',
        'Segmentation OCT Volume'
    )
    interpretations = (
        'Binary mask',
        'Probability',
        'R/G mask',
        'Label numbers',
        'Layer bits'
    )
    additional_types = [
        ('Segmentation 2D masked', 'R/G mask')
    ]

    index = {
        (a.AnnotationTypeName, a.Interpretation): a
        for a in AnnotationType.fetch_all(session)
    }
    expected = [
        (name, interpretation)
        for name in types
        for interpretation in interpretations
    ] + additional_types
    
    for name, interpretation in expected:
        if (name, interpretation) not in index:
            annotation_type = AnnotationType(
                AnnotationTypeName=name,
                Interpretation=interpretation
            )
            print('Adding annotation type:', name, interpretation)
            session.add(annotation_type)
    session.commit()
