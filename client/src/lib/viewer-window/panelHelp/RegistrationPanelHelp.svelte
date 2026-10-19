<p class="intro">
    Open a registration editor for images of one eye that are already in this
    window.
</p>
<section>
    <h2>Workflow</h2>
    <ul>
        <li>
            Images are grouped by patient and eye. Under Fixed and Moving, click
            one thumbnail in each.
        </li>
        <li>Choose an existing registration, or <strong>New</strong>.</li>
        <li>
            Click <strong>Open</strong>. The editor covers the window. Close
            returns to this viewer.
        </li>
        <li>
            Each image in the editor already has the point tool on. Place
            matching landmarks. Three pairs are enough for a transform. Spread
            them out.
        </li>
    </ul>
</section>
<section>
    <h2>Blend</h2>
    <ul>
        <li>
            Drag the bar between the images and the blend to change their
            height.
        </li>
        <li>
            Each image is a block headed by its public id. The colour slider
            goes from the original colours to luminosity times the picked
            colour. Opacity fades that image out. Fixed starts red and moving
            starts cyan.
        </li>
        <li>
            That second image stays out until the points define an affine
            between the two.
        </li>
    </ul>
</section>
<section>
    <h2>Series blend</h2>
    <ul>
        <li>
            Under Blend, outline any number of thumbnails from that eye, then
            click <strong>View blend</strong>.
        </li>
        <li>
            The selected images sit above the blend. The slider walks from the
            first image to the last, blending one consecutive pair at a time.
            Each image has its own opacity.
        </li>
        <li>
            This blend follows the registration graph, including a polynomial
            warp. An image with no path from the first one stays out.
        </li>
    </ul>
</section>
<section>
    <h2>Editing points</h2>
    <ul>
        <li>Left click on empty space to add a point.</li>
        <li>
            <kbd>Ctrl</kbd>-click places another point on top of an existing
            marker.
        </li>
        <li>Left click a point, then drag to move it.</li>
        <li>Right click a point to remove it.</li>
        <li>Hold Shift while clicking to pan and zoom.</li>
    </ul>
</section>
