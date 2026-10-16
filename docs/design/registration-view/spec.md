# Registration view

Issue: [#270](https://github.com/Eyened/eyened-platform/issues/270)

The registration panel becomes a launcher. It opens a full-window editor in the same viewer, on the existing graphics context, where the user places landmarks and sees a colour blend of the selected images in one coordinate space.

## Goal

A user reviewing registration can:

- choose two or more images that are already open, all from the same patient and the same eye
- choose an existing registration annotation, or create a new one
- place landmarks on those images with the point tool already on
- see those images added together in the fixed image's coordinates, each tinted by the automatic palette

Opacity, invert, a manual colour picker, a reset control, and further blend modes are out of this version. Issue 270 asks for those overlay controls. This version supplies show and hide (the per-image checkbox) and an automatic colour blend. The other controls wait until a later blend mode.

## Decisions

- The image list is the images already open in this viewer window (the current top row), not every image for the patient.
- Images are grouped by patient and eye. A registration never mixes eyes. An image with no laterality is its own group for that patient and is never mixed with a known eye.
- The user also chooses the registration annotation: an existing one for that patient and eye, or **New**.
- **New** creates the annotation when the editor opens, not when it is selected. Patient and laterality come from the group. Study and image id come from the first checked image. The annotation is otherwise created the same way as today's registration panel, including the current subtask when one is open.
- The editor is a full-window layer in this same window. It reuses the existing graphics context. It does not open a browser popup.
- The normal viewers stay mounted underneath. While the editor is open they do not paint. Closing the editor resumes them with their state intact.
- The editor uses the existing `Viewer` component, the existing point tool, the loaded images, and the existing registration graph. It does not reuse the top row, the side panels, or the main viewer.
- The first blend mode is additive colour. Colours are assigned in top-row order to the images currently included: the fixed image plus every checked image. A missing registration path does not change which images are included or which colour they have. Hiding an image (unchecking it) assigns the colours again over the images that remain.
- The palette depends on how many images are included:
  - 1: the image is shown untinted, in its original colours
  - 2: red, cyan
  - 3: red, green, blue
  - 4: red, green, blue, cyan
  - 5: red, green, blue, cyan, magenta
  - 6: red, green, blue, cyan, magenta, yellow
  - 7 or more: that six-colour list repeats
- "First" means first in current top-row order among the images that are checked, not the order the boxes were ticked. That rule picks the default fixed image and, for a new annotation, the study and image id. Groups themselves follow the top-row order of their first image.

## Architecture

`ViewerWindow` keeps the current layout mounted. Opening the editor sets a session on `ViewerWindowContext` and mounts one full-window layer above that layout. The layer has a close button at the top right.

There is one graphics canvas for the window. Each frame it is cleared, then every registered viewer paints into its own rectangle. While a registration session is set, that loop paints only the viewers that belong to the session. Viewers underneath stay registered and keep their state, but they are skipped. Closing the session removes the editor's viewers and the original viewers paint again.

The registration panel no longer lists annotations as activatable rows and no longer arms the point tool on the main viewer. It only groups images, picks an annotation, and opens the session.

## Components

### Registration panel

Replaces the body of `PanelRegistration`. For each group of open images that share a patient and an eye:

- a checkbox for every image in the group, in current top-row order, labelled with that image's public id
- the registration annotations for that patient, eye, and registration schema, plus **New**
- an **Open** button

**Open** is enabled only when that group has at least two images checked and an annotation choice (including **New**).

Annotations use the same patient, eye, and schema filter as the current panel. The list shows the creator and the annotation id, as today.

### Registration editor

A full-window layer. Close sits at the top right and ends the session. The top of the layer is one `Viewer` per checked image, in top-row order. Each viewer loads that image's points from the chosen annotation and arms the point tool immediately, using the same coordinate rules as today, including an OCT slice index. The user can pan and zoom inside each viewer.

Under that row, one more `Viewer` is the blend. Next to it:

- a radio that picks the fixed image
- a checkbox for every image that is not the fixed image

The fixed image starts as the first checked image. The other images start checked. The fixed image is always drawn. A checked image is drawn on top, warped into the fixed image's coordinates. Changing the radio makes the previous fixed image a checked overlay, so it stays visible, and the new fixed image is always drawn.

The blend is a new renderer used by that viewer. It is not `MultiImageRenderer`. It tints each included image with its assigned colour and adds the samples.

### Help

`RegistrationPanelHelp` describes the launcher and the editor. The old "create an annotation, then activate it on each main viewer" steps are removed.

## Data flow

Opening the editor writes nothing unless the choice is **New**. In that case it creates one empty registration annotation, then opens the session on it. If creation fails, the session does not open.

Each thumbnail reads points with `getPointsForImage` and writes them with `setPointsForImage` and `setFormAnnotationValue`, the same path the current panel uses. `RegistrationItemLoader` already watches those annotations and recomputes registration paths. The blend reads that graph. It does not keep a second copy of the transform.

For each checked image, the blend asks the graph for a path into the fixed image. When a path exists, the image is warped and added. When it does not, that image is left out and the fixed image still shows. Placing enough matching points makes the path appear and the overlay joins the blend.

If the user cannot edit the annotation, the points still show and the point tool does not move them.

Other registration annotations already loaded in the window still feed the same graph, as they do today. Editing the chosen annotation updates that annotation's points, and the loader recomputes from the full set.

The session is not written to the view-state URL. Closing it drops the fixed-image choice and the overlay checkboxes. The panel stays mounted, so its checks and annotation choice remain.

## Errors

- **Open** stays disabled until the group has two checked images and an annotation choice.
- A failed create leaves the editor closed.
- A checked image with no registration path is not drawn. It still counts toward the palette.
- Closing the editor always clears the session and resumes the viewers underneath, including when the editor fails while opening.

## Testing

- Grouping is a pure function. Tests cover splitting open images by patient and eye, keeping an image with no laterality in its own group, and enabling **Open** only with two checked images and an annotation choice.
- Colour assignment is a pure function. Tests cover two images (red, cyan), three images (red, green, blue), a fourth colour, and reassignment when one image is hidden. One included image is untinted.
- What gets drawn is tested without a graphics canvas. The fixed image is always drawn. A checked image is drawn only when a path into the fixed image exists. An unchecked image is not drawn. A checked image with no path still receives a palette colour.
- A panel component test covers **New**: selecting it does not create an annotation; opening does; a failed create leaves the editor closed.
- The paint loop is tested on the viewer window context. While a session is set, a frame paints the session's viewers and skips the others. After the session is cleared, only the original viewers paint.
- Existing point-tool tests stay as they are. This work does not change how points are stored.

## Out of scope

- Opacity, invert, a manual colour, reset, and any blend mode other than additive colour.
- A separate browser window.
- Rebuilding the top row, the side panels, or the main viewer.
- Changing the point storage format or the registration math.
- Persisting the editor's fixed image and checkboxes across close.
