<p class="intro">
    Place and review ETDRS grids on 2D enface images. The grid is centered on
    the fovea and scaled from the fovea-to-optic-disc distance.
</p>

<section>
    <h2>Automatic vs manual</h2>
    <ul>
        <li>
            <strong>Automatic</strong> — preview AI-detected landmarks from cf_keypoints
            (read-only; does not create an annotation).
        </li>
        <li>
            <strong>Manual</strong> — create an annotation, then use the edit tool
            to place landmarks that are saved to the database.
        </li>
    </ul>
</section>

<section>
    <h2>Workflow</h2>
    <ul>
        <li>Optionally toggle Automatic to preview AI keypoints.</li>
        <li>Click Create new to add a manual annotation.</li>
    </ul>
    <p>
        The edit tool on the annotation will be activated automatically. You can
        also activate/deactivate it manually.
    </p>
    <ul>
        <li>Left click in the image to set the fovea.</li>
        <li>Right click to set the optic disc edge.</li>
    </ul>
    <p>Use show/hide to toggle the grid overlay.</p>
    <p>
        Note: the grid overlay and tool for editing markers will remain active
        if you close the ETDRS panel. Deactivate the tool if you do not want to
        edit the markers anymore.
    </p>
</section>

<section>
    <h2>Grid settings</h2>
    <p>
        ETDRS radius fraction (default 0.85) scales the grid: that fraction of
        the fovea–disc distance is treated as 3 mm.
    </p>
    <p>
        Circles represent diameters of 1 mm (central), 3 mm (inner), and 6 mm
        (outer) ETDRS subfields.
    </p>
</section>

<section>
    <h2>Keyboard shortcuts</h2>
    Press the following keys to cycle through the subfield circles:
    <dl>
        <div class="row">
            <dt>(C0, C1, C2)</dt>
            <dd><kbd>C</kbd></dd>
        </div>
        <div class="row">
            <dt>(I1, I2)</dt>
            <dd><kbd>I</kbd></dd>
        </div>
        <div class="row">
            <dt>(O1, O2)</dt>
            <dd><kbd>O</kbd></dd>
        </div>
    </dl>
    This will change the cursor in a circle with the selected diameter.
</section>
