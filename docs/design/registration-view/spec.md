# Registration view

Issue: [#270](https://github.com/Eyened/eyened-platform/issues/270)

The registration panel is a launcher. It opens a full-window editor in the same viewer, on the existing graphics context, where the user places landmarks and sees one fixed image and one moving image added together.

## Goal

A user reviewing registration can:

- choose one fixed image and one moving image that are already open, both from the same patient and the same eye
- choose an existing registration annotation they can edit, or create a new one
- place landmarks on those two images with the point tool already on
- see the moving image warped into the fixed image by a direct affine

Each image can fade between its original colours and luminosity times a picked colour, and each has its own opacity.

## Decisions

- The image list is the images already open in this viewer window (the current top row), not every image for the patient. Volumes and slice stacks (`is2D === false`) are skipped. Enface projections stay.
- Images are grouped by patient and eye. A registration never mixes eyes. An image with no laterality stays in an unset group for that patient.
- Within a group, Fixed and Moving are two thumbnail strips in top-row order. The selected thumbnail has an outline. Hover shows the public id. The same image cannot be both.
- The annotation list is registrations for that patient, eye, and schema that the current user can edit, plus **New**.
- **New** creates the annotation when Open is clicked. Patient and laterality come from the group. Study and image id come from the fixed image. The current subtask is included when a task is open. A failed create does not open the editor. A second click while create is in flight does not create twice.
- The editor is a full-window layer in this window. It reuses the existing graphics context. It does not open a browser popup.
- The normal viewers stay mounted underneath and do not paint while the editor is open. Closing resumes them.
- The editor uses the existing `Viewer`, point tool, loaded images, and registration graph. It does not reuse the top row, the side panels, or the main viewer.
- The blend is one fixed shader for two images. The affine matrix, tint, and opacity are uniforms. Point drags do not recompile it.
- Only a direct affine edge between the two images is used. The moving image stays out until that edge exists, and it is not drawn where the warp falls outside that image.
- The session is not written to the view-state URL.

## Editor

Close sits at the top right. Above a draggable separator are the two images, each with the point tool armed. Below is the blend. The separator works like the one between the normal top row and the main viewer, and starts at 34% of the window.

The blend panel has one block per image, headed by its public id:

- a slider from original colour (left) to luminosity times the picked colour (right), plus a colour picker
- an opacity slider

Fixed starts fully red. Moving starts fully cyan. Both start fully opaque.

## Data flow

Points use `getPointsForImage` / `setPointsForImage` / `setFormAnnotationValue`. Keys are the instance public id, the same as the rest of the viewer. `RegistrationItemLoader` recomputes the registration graph. The blend reads the direct affine from that graph.

A drag moves a point by the cursor delta from where the press started, including a short move and a grab away from the marker centre.

If the user cannot edit the annotation, the points still show and the point tool does not move them.

## Series blend

A separate section in the same panel opens a second full-window view. It is not the two-image editor.

- Thumbnails for that eye can be selected in any number. The outline shows the selection. **View blend** needs at least two.
- The series order is top-row order among the selected images.
- The overlay shows those images on top and the blend below, with the same draggable separator, starting at 34%.
- The side panel has one opacity slider per image, and one series slider. The series slider at the left shows only the first image. Moving it right blends into the next image, then the one after that, one consecutive pair at a time, until the last image is the only one shown.
- Per-image opacity multiplies that pair weight.
- The first image is the coordinate space. Each other image is warped by a baked path from the registration graph. That path can be affine, parabolic, composite, or enface. The shader is compiled when those paths change. The sliders only update weight uniforms.
- An image with no bakeable path from the first image adds nothing.
- Samples that fall outside an image are not drawn.
- Opening either overlay closes the other. Background viewers stay mounted and do not paint until the overlay closes.

## Out of scope

- Multi-hop or non-affine warps in the two-image editor
- Colour tint in the series blend
- Invert, reset, and blend modes other than these two
- A separate browser window
- Changing point storage or the registration math
