<p class="intro">
    Draw, edit, and review segmentations on the current image plane.
    Segmentations are grouped by creator and can include your own annotations,
    those from other graders, and AI model outputs.
</p>

<section>
    <h2>Getting started</h2>

    <details class="subsection" open>
        <summary>Segmentation list</summary>
        <div class="subsection-body">
            <ul>
                <li>
                    Click a segmentation name to select it for editing. The
                    active item is highlighted with a cyan border.
                </li>
                <li>
                    Hover a list item to briefly highlight its overlay on the
                    image.
                </li>
                <li>
                    Use the show/hide icon to toggle an individual segmentation.
                    Right-click the icon to show only that segmentation.
                </li>
                <li>
                    Expand a creator group (▼/►) to show or hide all
                    segmentations from that user. AI model segmentations appear
                    in a separate AI group.
                </li>
                <li>
                    Empty segmentations on the current slice appear dimmed;
                    editable ones can still be selected to start drawing.
                </li>
            </ul>
        </div>
    </details>

    <details class="subsection">
        <summary>Opacity and overlay</summary>
        <div class="subsection-body">
            <p>
                The opacity slider at the top controls how strongly all visible
                segmentation overlays are blended with the image. Lower opacity
                helps compare boundaries against the underlying fundus or
                B-scan.
            </p>
            <p>
                For binary and questionable segmentations you can change the
                overlay color with the color picker on each list item.
                Multi-class and multi-label segmentations use fixed colors per
                subfeature.
            </p>
        </div>
    </details>

    <details class="subsection">
        <summary>Creating a segmentation</summary>
        <div class="subsection-body">
            <p>
                Search for a feature name at the bottom of the panel to quickly
                create a
                <strong>Questionable</strong> segmentation covering the full image.
            </p>
            <p>
                Click <strong>Advanced…</strong> to open the full creation dialog
                with placement, type, and feature options (see Advanced options below).
            </p>
            <p>
                New segmentations are activated automatically so you can start
                drawing immediately.
            </p>
        </div>
    </details>
</section>

<section>
    <h2>Segmentation types</h2>
    <p>
        Each list item shows a type tag in square brackets, for example
        <kbd>[Q]</kbd> or <kbd>[P]</kbd>. The type determines how pixels are
        stored and which tools are available.
    </p>

    <details class="subsection">
        <summary>Questionable (Q) — DualBitMask</summary>
        <div class="subsection-body">
            <p>
                Stores both a definite mask and a separate questionable region.
                Use the Questionable toggle in the toolbar while drawing to mark
                uncertain areas without affecting the main segmentation.
            </p>
        </div>
    </details>

    <details class="subsection">
        <summary>Binary (B)</summary>
        <div class="subsection-body">
            <p>A simple on/off mask per pixel.</p>
        </div>
    </details>

    <details class="subsection">
        <summary>Probability (P)</summary>
        <div class="subsection-body">
            <p>
                Stores a soft probability value (0–1) per pixel instead of a
                hard label. When selected, a threshold slider appears to control
                the displayed contour. The Enhance tool is available only for
                probability segmentations.
            </p>
        </div>
    </details>

    <details class="subsection">
        <summary>Multi-class (MC) and Multi-label (ML)</summary>
        <div class="subsection-body">
            <p>
                Both types use a parent feature with subfeatures. Multi-class
                allows one class per pixel (radio selection); multi-label allows
                overlapping classes (checkbox selection).
            </p>
            <p>
                When active, choose which subfeature(s) to paint from the layer
                list. Toggle individual layer visibility with the show/hide icon
                next to each subfeature. Multi-class also provides separate
                opacity sliders for the active class and all other classes.
            </p>
        </div>
    </details>
</section>

<section>
    <h2>Drawing and editing tools</h2>
    <p>
        Activate a tool from the toolbar below the opacity slider. Only one
        primary editing tool (brush, polygon, or enhance) can be active at a
        time. Tools are disabled until you select an editable segmentation —
        model segmentations must be duplicated first. Changes are saved
        automatically; a sync indicator (green / orange / red) appears when
        changes are saved.
    </p>

    <details class="subsection" open>
        <summary>Brush</summary>
        <div class="subsection-body">
            <p>
                Paint or erase freehand strokes. Hold the paint or erase
                shortcut key, or use the Drawing / Erasing toggle at the bottom
                of the toolbar.
            </p>
            <p>
                When the brush is active, a radius control appears. Adjust size
                with number keys, <kbd>+</kbd>/<kbd>−</kbd>, or
                <kbd>Alt</kbd> + scroll / drag.
            </p>
        </div>
    </details>

    <details class="subsection">
        <summary>Polygon</summary>
        <div class="subsection-body">
            <p>
                Draw shaped by dragging around the region. Left-click or <kbd
                    >Q</kbd
                >
                adds regions; right-click or <kbd>W</kbd> erases regions.
            </p>
        </div>
    </details>

    <details class="subsection">
        <summary>Enhance (probability only)</summary>
        <div class="subsection-body">
            <p>
                Refines soft probability maps by pushing values toward 0 or 1
                under the brush. Adjust <strong>Hardness</strong> for edge
                sharpness and
                <strong>Pressure</strong> for effect strength while the tool is active.
            </p>
        </div>
    </details>

    <details class="subsection">
        <summary>Dilate / erode and Questionable</summary>
        <div class="subsection-body">
            <p>
                <strong>Dilate / Erode</strong> — while active, brush strokes expand
                or shrink existing boundaries instead of painting raw pixels. Useful
                for fine-tuning edges.
            </p>
            <p>
                <strong>Questionable</strong> — while active (Q-type only), strokes
                mark uncertain regions in the questionable bit plane rather than
                the main mask.
            </p>
        </div>
    </details>

    <details class="subsection">
        <summary>Undo and redo</summary>
        <div class="subsection-body">
            <p>
                Undo and redo apply per segmentation and per B-scan slice in OCT
                volumes.
            </p>
        </div>
    </details>
</section>

<section>
    <h2>Keyboard shortcuts</h2>
    <p>
        Shortcuts apply when the viewer has focus and a segmentation tool is
        relevant.
    </p>
    <dl>
        {#each [{ action: "Paint (hold)", keys: "Q" }, { action: "Erase (hold)", keys: "W" }, { action: "Pick feature / segmentation under cursor", keys: "A" }, { action: "Set brush radius 1–9", keys: "1 – 9" }, { action: "Increase / decrease brush radius", keys: "+ / −" }, { action: "Adjust brush radius", keys: "Alt + scroll or Alt + drag" }] as { action, keys }}
            <div class="row">
                <dt>{action}</dt>
                <dd><kbd>{keys}</kbd></dd>
            </div>
        {/each}
    </dl>
</section>

<section>
    <h2>Advanced options</h2>
    <p>
        Expand the handle (►) at the bottom of an active segmentation to access
        additional tools. Some options depend on segmentation type or edit
        permissions.
    </p>

    <details class="subsection">
        <summary>Advanced creation dialog</summary>
        <div class="subsection-body">
            <p>
                Opened via <strong>Advanced…</strong> at the bottom of the panel,
                or automatically after drawing a region box on the image.
            </p>
            <ul>
                <li>
                    <strong>Full image</strong> — segmentation covers the entire
                    image plane at native resolution.
                </li>
                <li>
                    <strong>Region box</strong> — draw a rectangle on the image to
                    define which area is annotated. Set separate segmentation width
                    and height to control the internal resolution.
                </li>
                <li>
                    Choose the type (Q, B, P, multi-class, multi-label) and
                    feature before clicking Create.
                </li>
            </ul>
        </div>
    </details>

    <details class="subsection">
        <summary>Import from another segmentation</summary>
        <div class="subsection-body">
            <p>
                Copies mask data from another segmentation on the current slice
                into the selected one. Pick the source from a list in the
                dialog. Useful for initializing a new annotation from an AI
                output or a colleague's work.
            </p>
        </div>
    </details>

    <details class="subsection">
        <summary>Duplicate</summary>
        <div class="subsection-body">
            <p>
                Creates an editable copy of the current segmentation. For AI
                model segmentations, use the quick <strong>Duplicate</strong> button
                on the list item.
            </p>
            <p>
                In the expanded options panel you can choose the target type (Q,
                B, or P) and, for OCT volumes, duplicate the full volume or only
                the current B-scan.
            </p>
        </div>
    </details>

    <details class="subsection">
        <summary>Reference mask</summary>
        <div class="subsection-body">
            <p>
                Links this segmentation to another that acts as a conditional
                mask. That is: the final segmentation is the intersection of
                this segmentation and the reference segmentation. You can set or
                update the reference via
                <strong>Update reference mask</strong>; toggle masked vs
                unmasked display once a reference is assigned.
            </p>
        </div>
    </details>

    <details class="subsection">
        <summary>Connected components</summary>
        <div class="subsection-body">
            <p>
                For binary and questionable segmentations, enable
                <strong>Show connected components</strong> to visualize separate
                blobs in different colors. Helpful when reviewing fragmented regions
                or counting disconnected areas.
            </p>
        </div>
    </details>

    <details class="subsection">
        <summary>Threshold (probability)</summary>
        <div class="subsection-body">
            <p>
                When a probability segmentation is active, drag the threshold
                slider to change the cutoff used for display and export. The
                value is saved to the database when you release the slider.
            </p>
        </div>
    </details>

    <details class="subsection">
        <summary>AI model segmentations</summary>
        <div class="subsection-body">
            <p>
                Model outputs appear under the AI group and are read-only. They
                cannot be edited directly — duplicate them first to create an
                editable grader segmentation you own.
            </p>
            <p>
                Use show/hide on the AI group header to toggle all model
                overlays at once.
            </p>
        </div>
    </details>
</section>
