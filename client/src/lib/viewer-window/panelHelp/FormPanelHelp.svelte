<p class="intro">
    Create and fill structured grading forms attached to the patient, study, or
    current image.
</p>

<section>
    <h2>Creating forms</h2>
    <ul>
        <li>Select a form type from the dropdown and click Create new form.</li>
        <li>
            When a task is active, the form type may be pre-selected from the
            task definition config.
        </li>
        <li>A shortcut button may appear for frequently used forms.</li>
    </ul>
</section>

<section>
    <h2>Scope</h2>
    <p>Study-eye forms are filtered by study date and laterality.</p>
    <p>Image-level forms are shown for the current image.</p>
    <p>
        ETDRS and registration schemas are managed in their dedicated panels,
        not here.
    </p>
</section>

<section>
    <h2>Points</h2>
    <ul>
        <li>
            Activate a point field, then left-click empty image to place a
            point. Drag a point to move it. Click a point without dragging to
            cycle its grade. Right-click a point to remove it.
        </li>
        <li>
            <kbd>Ctrl</kbd>-click places another point even on top of an
            existing marker, so two points can sit closer than the marker
            itself. That click does not cycle or drag.
        </li>
        <li>
            A required grade starts on the first value as soon as the point is
            placed.
        </li>
        <li>
            An optional grade stays unset until you set it. The form still
            offers a blank choice for that grade.
        </li>
    </ul>
</section>

<section>
    <h2>Grade</h2>
    <p>
        Click a point without dragging it, or hover it and press <kbd>C</kbd>,
        to cycle its grade. Further clicks or presses move through the remaining
        values and wrap back to the first. On an optional grade, the first click
        or press sets the first value.
    </p>
    <dl>
        <div class="row">
            <dt>Cycle the point's grade</dt>
            <dd>Click or <kbd>C</kbd></dd>
        </div>
        <div class="row">
            <dt>Place a point on top of another</dt>
            <dd><kbd>Ctrl</kbd> + click</dd>
        </div>
    </dl>
</section>
