import json
import numpy as np
from PIL import Image
import io
import base64

_style = '''
<style>
table {
    width: 100%;
    border-collapse: collapse;
}

table, th, td {
    border: 1px solid black;
}

th, td {
    padding: 8px;
    text-align: left;
}

tr:nth-child(even) {
    background-color: #f2f2f2;
}

tr:hover {
    background-color: #ddd;
}
div#segmentation-container {
    display: grid;
    grid-template-columns: 1fr 1fr;    
    color: white;
    background-color: black;
}
div#segmentation-container div {
    justify-self: center;
}
div#segmentation-container h2 {
    margin-left: 1em;
}
div#grid-img-container {
    position: relative;
    width: 30em;
    height: 30em;
    overflow: auto;
    resize: both;
}
div#grid-img-container img {
    width: 100%;
    height: 100%;
    object-fit: contain;
}
div#grid-img-container svg {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    }
</style>
'''

class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        else:
            return super(NumpyEncoder, self).default(obj)

def make_base64(img, size=(256, 256)):
    pil_img = Image.fromarray(img)
    if size:
        pil_img.thumbnail(size)

    byte_stream = io.BytesIO()
    pil_img.save(byte_stream, format='PNG')
    # Encode PNG image to base64 string
    img_base64 = base64.b64encode(byte_stream.getvalue()).decode('utf-8')

    return f'data:image/png;base64,{img_base64}'

def make_img(img, size=(384, 384)):
    return f'<img src="{make_base64(img, size)}"/>'

class Report:

    def __init__(self, feature_images, etdrs, field_names):
        self.feature_images = feature_images
        self.etdrs = etdrs
        self.field_names = field_names
        self.make_summary()

    def make_summary(self):
        self.summaries = {
            feature_name: self.etdrs.get_summary(img, self.field_names)
            for feature_name, img in self.feature_images.items()
        }

    def export_html(self, filename, image, name):
        html = self.generate_html_report(image, name)
        with open(filename, 'w') as f:
            f.write(html)

    def export_json(self, filename):
        with open(filename, 'w') as f:
            json.dump(self.summaries, f, cls=NumpyEncoder)

    def export(self, folder, image, name, export_html=True, export_json=True):
        if export_html:
            self.export_html(f'{folder}/report.html', image, name)
        if export_json:
            self.export_json(f'{folder}/report.json')

    def generate_html_table(self):
        measurements = 'area', 'count'
        headers = [
            "Field"] + [f"{name}_{measurement}" for name in self.summaries for measurement in measurements]
        table = [headers]
        for field in self.field_names:
            row = [field]
            for name in self.summaries:
                for measurement in measurements:
                    key = f"{field}_{measurement}"
                    row.append(self.summaries[name].get(key, ""))
            table.append(row)

        def cell(value, i):
            if type(value) == float:
                value = f'{value:.2f}'
            t = 'th' if i == 0 else 'td'
            return f'<{t}>{value}</{t}>'

        def map_row(row):
            return f'<tr>{"".join(cell(v, i) for i, v in enumerate(row))}</tr>'

        html = [
            "<table><thead><tr>",
            *[cell(header, 0) for header in table[0]],
            "</tr></thead><tbody>",
            *[map_row(row)for row in table[1:]],
            "</tbody></table>"
        ]
        return "\n".join(html)

    def generate_html_report(self, image, name):
        
        etdrs_img = make_base64(image)
        h, w = image.shape[:2]
        base_grid = self.etdrs.create_svg(color='white', crop=False)
        grid_img = f'''
        <div id="grid-img-container">
        <img src="{etdrs_img}" width="{w}px" height="{h}px">
        {base_grid}
        </div>
        '''
        
        table = self.generate_html_table()

        grids = []
        for feature_name, summary in self.summaries.items():

            count = {k[:3]: f'{v}' for k,
                     v in summary.items() if k.endswith('count')}
            area = {k[:3]: f'{v:.2f}' for k,
                    v in summary.items() if k.endswith('area')}
            svg1 = self.etdrs.create_svg(count, crop=True)
            svg2 = self.etdrs.create_svg(area, crop=True)

            imgs = f'<div style="display: flex;">{svg1}{svg2}</div>'
            grids.append(f'<div><h2>{feature_name}</h2>{imgs}</div>')

        grids = ''.join(grids)

        overlays = {}

        for feature_name, img in self.feature_images.items():
            a = np.copy(image)
            a[img] = 255
            overlays[feature_name] = a
        imgs = ''.join(
            f'<div><h2>{feature_name}</h2>{make_img(img)}</div>' for feature_name, img in overlays.items())
        imgs = f'<div id="segmentation-container">{imgs}</div>'


        
        return f'''
                <!doctype html><html>{_style}
                <body>
                <h1>{name} ({self.etdrs.laterality})</h1>
                <h2>Segmentation output:</h2>
                {imgs}
                <h2>ETDRS grid</h2>
                {grid_img}
                <h2>Field measurements table:</h2>
                <p>Area in mm&sup2;, count in number of connected components.</p>
                {table}
                <h2>Field measurements grids:</h2>
                <p>Left: count (number of connected components)</p>
                <p>Right: area in mm&sup2;</p>
                {grids}
                </body></html>
                '''
