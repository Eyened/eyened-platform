<p class="intro">
    Adjust how the image is displayed without changing the underlying data.
    Render modes apply on the fly in the viewer.
</p>

<section>
    <h2>Enface render modes</h2>
    <p>
        Available for 2D enface images. Press the shortcut key while the viewer
        has focus, or select a mode in the Rendering panel.
    </p>
    <table class="help-table">
        <thead>
            <tr>
                <th scope="col">Mode</th>
                <th scope="col" class="shortcut">Shortcut</th>
                <th scope="col">Description</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>Original</td>
                <td class="shortcut"><kbd>R</kbd></td>
                <td
                    >Unmodified image as stored; use as the baseline for
                    grading.</td
                >
            </tr>
            <tr>
                <td>Luminance</td>
                <td class="shortcut"><kbd>L</kbd></td>
                <td
                    >Grayscale weighted for human brightness; reduces color
                    distraction when assessing structure.</td
                >
            </tr>
            <tr>
                <td>Contrast enhanced</td>
                <td class="shortcut"><kbd>E</kbd></td>
                <td
                    >Increases global and local contrast; helps faint vessels,
                    drusen, and lesions stand out.</td
                >
            </tr>
            <tr>
                <td>Color balanced</td>
                <td class="shortcut"><kbd>B</kbd></td>
                <td
                    >Corrects illumination by mapping per-channel mean and
                    standard deviation to fixed reference values.</td
                >
            </tr>
            <tr>
                <td>CLAHE</td>
                <td class="shortcut"><kbd>H</kbd></td>
                <td
                    >Contrast-limited adaptive histogram equalization: enhances
                    local detail, may amplify noise in flat regions.</td
                >
            </tr>
            <tr>
                <td>Sharpened</td>
                <td class="shortcut"><kbd>S</kbd></td>
                <td
                    >Applies a sharpening filter to enhance edges and fine
                    detail. Similar to contrast enhanced, but with more natural
                    colors.</td
                >
            </tr>
            <tr>
                <td>Histogram matched</td>
                <td class="shortcut"><kbd>M</kbd></td>
                <td
                    >Matches intensities to a reference histogram. Should give a
                    more consistent appearance across images, but may have
                    artifacts when channels (in particular red) are saturated.</td
                >
            </tr>
            <tr>
                <td>Red</td>
                <td class="shortcut"><span class="none">—</span></td>
                <td
                    >Red channel only. Sometimes useful for inspecting deeper
                    structures or choroid.</td
                >
            </tr>
            <tr>
                <td>Green</td>
                <td class="shortcut"><span class="none">—</span></td>
                <td
                    >Green channel only. Sometimes useful for hemorrhages or
                    pigmentary changes.</td
                >
            </tr>
            <tr>
                <td>Blue</td>
                <td class="shortcut"><span class="none">—</span></td>
                <td
                    >Blue channel only. Sometimes useful to identify reticular
                    pseudodrusen and differentiate them from normal drusen.</td
                >
            </tr>
        </tbody>
    </table>
</section>

<section>
    <h2>OCT volumes (axial view)</h2>
    <p>Only a subset of render modes is available when viewing OCT B-scans.</p>
    <table class="help-table">
        <thead>
            <tr>
                <th scope="col">Mode</th>
                <th scope="col" class="shortcut">Shortcut</th>
                <th scope="col">Description</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>Original</td>
                <td class="shortcut"><kbd>R</kbd></td>
                <td>Original B-scan intensities.</td>
            </tr>
            <tr>
                <td>CLAHE</td>
                <td class="shortcut"><kbd>H</kbd></td>
                <td>Local contrast enhancement.</td>
            </tr>
        </tbody>
    </table>
</section>

<section>
    <h2>Windowlevel &amp; stretch</h2>
    <p>
        Windowlevel sliders to brightness and contrast continuously on top of
        the selected render mode. Use both ends of the slider to set the low and
        high limits of the window.
    </p>
    <p>
        For OCT volumes, stretch controls change the vertical scaling of B-scans
        in the axial view.
    </p>
</section>
