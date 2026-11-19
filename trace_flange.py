"""Extract a flange silhouette and circular hole centres from a front-on image."""

import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

ROOT = Path(__file__).resolve().parent


def simplify(points, tolerance):
    a, b = points[0], points[-1]
    delta = b - a
    if np.linalg.norm(delta) < 1e-12:
        distances = np.linalg.norm(points - a, axis=1)
    else:
        distances = np.abs(delta[0] * (points[:, 1] - a[1])
                           - delta[1] * (points[:, 0] - a[0])) / np.linalg.norm(delta)
    index = int(np.argmax(distances))
    if distances[index] <= tolerance:
        return [a, b]
    return simplify(points[:index + 1], tolerance)[:-1] + simplify(points[index:], tolerance)


def contour(mask, tolerance=2.5):
    padded = np.pad(mask, 1)
    edges = {}
    for neighbor, start, end in [
        (padded[:-2, 1:-1], (0, 0), (1, 0)),
        (padded[1:-1, 2:], (1, 0), (1, 1)),
        (padded[2:, 1:-1], (1, 1), (0, 1)),
        (padded[1:-1, :-2], (0, 1), (0, 0)),
    ]:
        for y, x in zip(*np.nonzero(mask & ~neighbor)):
            a, b = (int(x + start[0]), int(y + start[1])), (int(x + end[0]), int(y + end[1]))
            if a in edges:
                raise ValueError("Ambiguous diagonal boundary; cannot trace safely")
            edges[a] = b
    first = min(edges, key=lambda point: (point[1], point[0]))
    points, current = [], first
    while True:
        points.append(current)
        current = edges.pop(current)
        if current == first:
            break
    if edges:
        raise ValueError("Multiple boundaries found in a filled contour")
    points = np.asarray(points, dtype=float)
    split = int(np.argmax(np.linalg.norm(points - points[0], axis=1)))
    return np.asarray(
        simplify(points[:split + 1], tolerance)[:-1]
        + simplify(np.vstack([points[split:], points[:1]]), tolerance)[:-1]
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    args = parser.parse_args()
    image = Image.open(args.image).convert("RGB")
    gray = np.asarray(image.convert("L"))
    dark = ndimage.binary_closing(gray < 160, structure=np.ones((3, 3)))
    labels, _ = ndimage.label(dark)
    counts = np.bincount(labels.ravel())
    counts[0] = 0
    material = labels == counts.argmax()
    outer_mask = ndimage.binary_fill_holes(material)
    hole_labels, count = ndimage.label(outer_mask & ~material)
    areas = np.bincount(hole_labels.ravel())
    areas[0] = 0
    opening_id = areas.argmax()
    opening_mask = ndimage.binary_fill_holes(hole_labels == opening_id)
    bolts = []
    for label in range(1, count + 1):
        area = areas[label]
        if label == opening_id or area < 150:
            continue
        y, x = ndimage.center_of_mass(hole_labels == label)
        yy, xx = np.nonzero(hole_labels == label)
        ratio = (xx.max() - xx.min() + 1) / (yy.max() - yy.min() + 1)
        if not 0.75 < ratio < 1.3:
            raise ValueError(f"Unrecognized non-circular aperture: label {label}")
        bolts.append([x + 0.5, y + 0.5])
    if len(bolts) != 16:
        raise ValueError(f"Expected 16 visible bolt apertures, found {len(bolts)}")
    outer = contour(outer_mask)
    inner = contour(opening_mask)
    yy, xx = np.nonzero(outer_mask)
    bounds = np.array([[xx.min(), yy.min()], [xx.max() + 1, yy.max() + 1]], dtype=float)
    center = bounds.mean(axis=0)
    dimensions = json.loads((ROOT / "dimensions.json").read_text(encoding="utf-8"))
    reference = np.array([dimensions["length_mm"], dimensions["flange_width_mm"]])
    scale = reference / (bounds[1] - bounds[0])

    def convert(points):
        return np.round((np.asarray(points) - center) * scale * [1, -1], 5).tolist()

    profile = {
        "reference_length_mm": reference[0],
        "reference_width_mm": reference[1],
        "outer_mm": convert(outer),
        "inner_mm": convert(inner),
        "bolt_centers_mm": convert(bolts),
        "source": {
            "image": args.image.name,
            "image_size_px": list(image.size),
            "silhouette_bounds_px": bounds.tolist(),
            "scale_mm_per_pixel_xy": scale.tolist(),
            "contour_simplification_px": 2.5,
            "note": "User-supplied gasket image; outline/opening/hole centres traced, not OEM CAD. Independent X/Y scale assumes the provisional 456 x 270 mm envelope. Thickness, bore diameters and handedness are not established by this image.",
        },
    }
    (ROOT / "flange_profile.json").write_text(json.dumps(profile, indent=2), encoding="utf-8")
    draw = ImageDraw.Draw(image)
    for points in [outer, inner]:
        draw.line([tuple(point) for point in points] + [tuple(points[0])], fill="#009bdf", width=4)
    for x, y in bolts:
        draw.line((x - 18, y, x + 18, y), fill="#ff7722", width=4)
        draw.line((x, y - 18, x, y + 18), fill="#ff7722", width=4)
    output = ROOT / "exports"
    output.mkdir(exist_ok=True)
    image.save(output / "flange_trace.png")
    print(f"Traced {len(outer)} outer vertices, {len(inner)} inner vertices, {len(bolts)} holes")
    print(f"Provisional scaling X/Y: {scale.tolist()} mm/pixel")


if __name__ == "__main__":
    main()
