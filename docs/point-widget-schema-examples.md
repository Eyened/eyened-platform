# Point fields in form schemas

Mark a field with `"x-eyened-widget": "keypoint"` to let graders place points on the image from the form.

How it behaves depends only on the **JSON Schema shape** of that field:

- a single `{x,y}` object → one point  
- an object with `additionalProperties` → points stored per image (image public_id is used as key)  
- an array → list of points  
- array items that allow `null` → deleted points leave a hole (e.g. for matching landmarks across images)

**Coordinate space** is also derived from shape:

- If the point object does **not** declare `index` → **2D / enface only** (fundus, `*_proj`). Placement on an OCT B-scan volume is rejected.
- If it declares optional `index` (`number` or `null`) → OCT volumes (slice index), enface projections (`index: null`), and plain 2D are all allowed.

Use **`title`** for the fixed name shown on the image (e.g. `"Fovea"`). Optional properties on each point (enums, short strings) can show instead when set. Prefer a short `title`; put longer help text in `description`.

Activate the tool from the form field, then click the image to place. Right-click a point to remove it. For enum properties, press **C** while hovering a point to cycle values.

In the form entry UI you can click on a coordinate to edit it manually (both the coordinates and optional label/text).

---

## 1. One point

```json
{
  "x-eyened-widget": "keypoint",
  "title": "Fovea",
  "type": "object",
  "properties": {
    "x": { "type": "number" },
    "y": { "type": "number" }
  },
  "required": ["x", "y"]
}
```

Saved value:

```json
{ "x": 1204.5, "y": 890.0 }
```

One marker. A new click moves it. Label on the image: **Fovea**.

---

## 2. Several points

```json
{
  "x-eyened-widget": "keypoint",
  "title": "Lesions",
  "type": "array",
  "items": {
    "type": "object",
    "properties": {
      "x": { "type": "number" },
      "y": { "type": "number" }
    },
    "required": ["x", "y"]
  }
}
```

Saved value:

```json
[
  { "x": 100, "y": 200 },
  { "x": 300, "y": 400 }
]
```

Each click adds a point. Removing a point closes the gap. Labels: **1**, **2**, …

---

## 3. Several points with extra fields

Extra properties on each point (string enums and free-text strings) are editable in the form and can appear next to the marker.

```json
{
  "x-eyened-widget": "keypoint",
  "title": "AV nicking",
  "type": "array",
  "items": {
    "type": "object",
    "properties": {
      "x": { "type": "number" },
      "y": { "type": "number" },
      "severity": {
        "type": "string",
        "enum": ["grade1", "grade2", "grade3"]
      },
      "note": { "type": "string" }
    },
    "required": ["x", "y"]
  }
}
```

Saved value:

```json
[
  { "x": 10, "y": 20, "severity": "grade2" },
  { "x": 30, "y": 40, "note": "temporal" }
]
```

On the image you might see **1:grade2** and **2:temporal** once those extras are set.

---

## 4. One point per image

When the same annotation covers several images, store one point under each image id.

```json
{
  "x-eyened-widget": "keypoint",
  "title": "Landmark",
  "type": "object",
  "additionalProperties": {
    "type": "object",
    "properties": {
      "x": { "type": "number" },
      "y": { "type": "number" }
    },
    "required": ["x", "y"]
  }
}
```

Saved value:

```json
{
  "img_aaa": { "x": 10, "y": 20 },
  "img_bbb": { "x": 30, "y": 40 }
}
```

While viewing an image, the tool only edits that image’s entry.

---

## 5. Several points per image

```json
{
  "x-eyened-widget": "keypoint",
  "title": "Landmarks",
  "type": "object",
  "additionalProperties": {
    "type": "array",
    "items": {
      "type": "object",
      "properties": {
        "x": { "type": "number" },
        "y": { "type": "number" }
      },
      "required": ["x", "y"]
    }
  }
}
```

Saved value:

```json
{
  "img_aaa": [
    { "x": 10, "y": 20 },
    { "x": 30, "y": 40 }
  ],
  "img_bbb": [{ "x": 5, "y": 6 }]
}
```

Same as a normal list, but scoped to the image you are viewing.

---

## 6. Matched landmarks across images (holes allowed)

Use this when point *i* on one image is the same landmark as point *i* on another. Allow `null` in the list so deleting a mid-list point keeps later indices aligned. Declare optional `index` so the same annotation can cover fundus, OCT B-scans, and enface `*_proj` images (built-in Pointset registration).

```json
{
  "x-eyened-widget": "keypoint",
  "title": "Pointset registration",
  "type": "object",
  "additionalProperties": {
    "type": "array",
    "items": {
      "oneOf": [
        {
          "type": "object",
          "properties": {
            "x": { "type": "number" },
            "y": { "type": "number" },
            "index": { "type": ["number", "null"] }
          },
          "required": ["x", "y"]
        },
        { "type": "null" }
      ]
    }
  }
}
```

Saved value:

```json
{
  "hudf99df": [
    { "x": 1470.6, "y": 239.8, "index": 0 },
    { "x": 1972.4, "y": 681.9, "index": 0 }
  ],
  "f7da0s88_proj": [
    { "x": 900.4, "y": 358.2, "index": null },
    null
  ]
}
```

On the current image: a click fills the first empty slot; deleting a non-last point leaves `null`; deleting the last point shortens the list. This is the structure used by the built-in Registration panel.

---

## 7. Several named points on one form (e.g. fovea + disc)

Give each landmark its own field. Each gets `"x-eyened-widget": "keypoint"` and a short `title`.

```json
{
  "type": "object",
  "required": ["fovea", "disc_edge"],
  "properties": {
    "fovea": {
      "x-eyened-widget": "keypoint",
      "title": "Fovea",
      "type": "object",
      "properties": {
        "x": { "type": "number" },
        "y": { "type": "number" }
      },
      "required": ["x", "y"]
    },
    "disc_edge": {
      "x-eyened-widget": "keypoint",
      "title": "Disc edge",
      "type": "object",
      "properties": {
        "x": { "type": "number" },
        "y": { "type": "number" }
      },
      "required": ["x", "y"]
    }
  }
}
```

Saved value:

```json
{
  "fovea": { "x": 1000, "y": 800 },
  "disc_edge": { "x": 1400, "y": 900 }
}
```

Note: in a normal form, you only activate one field at a time. The ETDRS panel has a customized implementation to show and edit both markers together; the saved data is still this object.
