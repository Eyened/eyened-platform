import numpy as np
from functools import cached_property
from skimage import measure
import uuid


class ETDRS_masks:

    # naming convention: CSF = central subfield
    # [SNTI] = superior/nasal/temporal/inferior
    # [IO] = inner/outer

    subfields_9 = 'CSF', 'SIM', 'NIM', 'TIM', 'IIM', 'SOM', 'NOM', 'TOM', 'IOM'
    rings_3 = 'center', 'inner', 'outer'
    quadrants = 'superior_grid', 'nasal_grid', 'inferior_grid', 'temporal_grid'
    all_fields = tuple([*subfields_9, *rings_3, *quadrants, 'grid', 'total'])

    def __init__(self, h, w, fovea_x, fovea_y, resolution, laterality):
        '''
        h: height of the image
        w: width of the image
        fovea_x: x coordinate of the fovea
        fovea_y: y coordinate of the fovea
        resolution: resolution of the image in mm/pix 
            or: (resolution_x, resolution_y)

        laterality: laterality of the eye, 'R' or 'L'
        '''
        self.h = h
        self.w = w
        self.fovea_x = fovea_x
        self.fovea_y = fovea_y
        try:
            self.resolution_x, self.resolution_y = resolution
        except TypeError:
            self.resolution_x = resolution
            self.resolution_y = resolution
        self.laterality = laterality

    @cached_property
    def aspect_ratio(self):
        return self.resolution_y / self.resolution_x

    @cached_property
    def pixel_area(self):
        return self.resolution_x * self.resolution_y

    def calculate_area(self, binary_image):
        return float(binary_image.sum() * self.pixel_area)

    def calculate_count(self, binary_image):
        return self._calculate_count(measure.label(binary_image))

    def _calculate_count(self, labeled_image):
        return int(np.max(labeled_image))

    def calculate_largest_area(self, labeled_image):
        regions = measure.regionprops(labeled_image)
        return max((r.area for r in regions), default=0) * self.pixel_area

    def get_summary(self, binary_image, fields, include_area=True, include_count=True, include_largest=True):
        masked_images = {
            field: getattr(self, field) & binary_image
            for field in fields
        }
        result = {}
        for field, masked_image in masked_images.items():
            if include_area:
                result[f'{field}_area'] = self.calculate_area(masked_image)
            if include_largest or include_count:
                labeled_image = measure.label(masked_image)
                if include_count:
                    result[f'{field}_count'] = self._calculate_count(
                        labeled_image)
                if include_largest:
                    result[f'{field}_largest'] = self.calculate_largest_area(
                        labeled_image)

        return result

    @cached_property
    def dy(self):
        return np.arange(self.h)[:, None] - self.fovea_y

    @cached_property
    def dx(self):
        return np.arange(self.w)[None, :] - self.fovea_x

    @cached_property
    def theta(self):
        return np.arctan2(self.dy * self.resolution_y, self.dx * self.resolution_x) / (2 * np.pi)

    @cached_property
    def distance_to_fovea(self):
        dx = self.dx * self.resolution_x
        dy = self.dy * self.resolution_y
        return np.sqrt(dx * dx + dy * dy)

    @cached_property
    def total(self):
        return np.ones((self.h, self.w), dtype=bool)

    '''rings'''
    @cached_property
    def center(self):
        return self.distance_to_fovea < 0.5

    @cached_property
    def inner(self):
        return (self.distance_to_fovea < 1.5) & ~self.center

    @cached_property
    def outer(self):
        return (self.distance_to_fovea < 3) & ~(self.center | self.inner)

    @cached_property
    def grid(self):
        return self.center | self.inner | self.outer

    '''quadrants'''
    @cached_property
    def inferior(self):
        return (1/8 < self.theta) & (self.theta <= 3/8)

    @cached_property
    def left(self):
        return (3/8 < self.theta) | (self.theta <= -3/8)

    @cached_property
    def superior(self):
        return (- 3/8 < self.theta) & (self.theta <= -1/8)

    @cached_property
    def right(self):
        return (-1/8 < self.theta) & (self.theta <= 1/8)

    @cached_property
    def nasal(self):
        return self.right if self.laterality == 'R' else self.left

    @cached_property
    def temporal(self):
        return self.left if self.laterality == 'R' else self.right

    '''quadrants grid'''
    @cached_property
    def superior_grid(self):
        return self.superior & self.grid

    @cached_property
    def nasal_grid(self):
        return self.nasal & self.grid

    @cached_property
    def inferior_grid(self):
        return self.inferior & self.grid

    @cached_property
    def temporal_grid(self):
        return self.temporal & self.grid

    '''subfields'''
    @cached_property
    def CSF(self):
        return self.center

    @cached_property
    def SIM(self):
        return self.superior & self.inner

    @cached_property
    def NIM(self):
        return self.nasal & self.inner

    @cached_property
    def TIM(self):
        return self.temporal & self.inner

    @cached_property
    def IIM(self):
        return self.inferior & self.inner

    @cached_property
    def NOM(self):
        return self.nasal & self.outer

    @cached_property
    def TOM(self):
        return self.temporal & self.outer

    @cached_property
    def SOM(self):
        return self.superior & self.outer

    @cached_property
    def IOM(self):
        return self.inferior & self.outer

    def create_svg(self, text_dict=None, crop=True, color='black'):
        id_ = f"id_{uuid.uuid4().hex}"

        if text_dict is None:
            text_dict = {k: '' for k in ETDRS_masks.subfields_9}

        if self.laterality == 'R':
            # nasal right, temporal left
            translate = str.maketrans({'N': 'R', 'T': 'L'})
        else:
            # nasal left, temporal right
            translate = str.maketrans({'T': 'R', 'N': 'L'})
        text_query = {k.translate(translate): v for k, v in text_dict.items()}

        def svg_element(element, **kwargs):
            attr = ' '.join(f'{k}="{v}"' for k, v in kwargs.items())
            return f'<{element} {attr}/>'

        if crop:
            viewbox = '-3 -3 6 6'
            width = 240
            height = 240
        else:
            fx = self.fovea_x * self.resolution_x
            fy = self.fovea_y * self.resolution_y
            w = self.w * self.resolution_x
            h = self.h * self.resolution_y
            viewbox = f'{-fx} {-fy} {w} {h}'
            width = self.w
            height = self.h

        def svg_text(x, y, text):
            return f'<text x="{x}" y="{y}">{text}</text>'

        text_coordinates = [
            (0, 0, text_query.get('CSF', 'CSF')),
            (0, 1, text_query.get('IIM', 'IIM')),
            (0, -1, text_query.get('SIM', 'SIM')),
            (-1, 0, text_query.get('LIM', 'LIM')),
            (1, 0, text_query.get('RIM', 'RIM')),
            (0, 2.25, text_query.get('IOM', 'IOM')),
            (0, -2.25, text_query.get('SOM', 'SOM')),
            (-2.25, 0, text_query.get('LOM', 'LOM')),
            (2.25, 0, text_query.get('ROM', 'ROM'))
        ]

        svg_texts = "\n".join(svg_text(x, y, text)
                              for (x, y, text) in text_coordinates)

        d_inner = np.sqrt((0.5**2) / 2)
        d_outer = np.sqrt((3**2) / 2)

        svg_data = f"""
        <svg width="{width}" height="{height}" viewBox="{viewbox}" id="{id_}">
            <style>
                #{id_} circle, #{id_} line {{
                    stroke-width: 0.04;
                    stroke: {color};
                    fill: none;
                }}
                #{id_} text {{
                    fill: {color};
                    font-family: Verdana;
                    text-anchor: middle; 
                    dominant-baseline: middle;
                    font-size: 0.3px;
                }}
            </style>
            {svg_element('circle', cx=0, cy=0, r=3)}
            {svg_element('circle', cx=0, cy=0, r=1.5)}
            {svg_element('circle', cx=0, cy=0, r=0.5)}
            {svg_element('line', x1=-d_inner, y1=-d_inner, x2=-d_outer, y2=-d_outer)}
            {svg_element('line', x1=+d_inner, y1=-d_inner, x2=+d_outer, y2=-d_outer)}
            {svg_element('line', x1=-d_inner, y1=+d_inner, x2=-d_outer, y2=+d_outer)}
            {svg_element('line', x1=+d_inner, y1=+d_inner, x2=+d_outer, y2=+d_outer)}
            {svg_texts}
        
        </svg>
        """

        return svg_data

    def _repr_svg_(self):
        return self.create_svg({k: k for k in self.subfields_9})
