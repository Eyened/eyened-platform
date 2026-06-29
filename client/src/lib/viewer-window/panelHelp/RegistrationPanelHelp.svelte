<p class="intro">
    Define point-set registration between enface images of the same eye.
    Matching landmarks on each image are used to compute affine transforms.
</p>

<section>
    <h2>Workflow</h2>
    <ul>
        <li>
            Click <strong>Create new</strong> to start a registration annotation.
            Or activate an existing registration from the list. The active item will
            be highlighted in the list.
        </li>
        <li>
            It is recommended to open each image side-by-side, and activate the
            same item in each image.
        </li>
        <li>
            Place at least three matching point pairs across two images before a
            transform can be computed reliably. For the most accurate
            registration, try to avoid points that are very close to each other
            or on the same line. More points can be added for more accurate
            registration.
        </li>
        <li>Repeat for additional image pairs as needed.</li>
    </ul>
</section>

<section>
    <h2>Editing points</h2>
    <ul>
        <li>Left click on empty space to add a new point.</li>
        <li>Left click on an existing point, then drag to move.</li>
        <li>Right click on a point to remove it.</li>
        <li>Hold Shift while clicking to pan/zoom without editing.</li>
    </ul>
</section>

<section>
    <h2>Keyboard shortcuts</h2>
    <dl>
        <div class="row">
            <dt>Zoom to registration point 1–9</dt>
            <dd><kbd>0 – 9</kbd></dd>
        </div>
    </dl>
</section>

<section>
    <h2>Tip</h2>
    <p>
        Pick clearly identifiable structures (e.g. vessel crossings or
        bifurcations) that appear in both images.
    </p>
    <p>
        After identifying a point, you can press the corresponding number key to
        zoom to that point, then drag it to place it more accurately.
    </p>
</section>
