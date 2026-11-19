"""CAD-derived edge lengths and dimensioned inspection drawings."""

import csv
import json
import math
from html import escape

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def extract_edges(parts):
    result = []
    for name, part, _ in parts:
        for edge in part.val().Edges():
            length = edge.Length()
            if length < 1e-7:
                continue
            kind = edge.geomType()
            if kind == "LINE":
                points = [edge.startPoint(), edge.endPoint()]
            else:
                points, _ = edge.sample(max(24, min(256, math.ceil(length / 2))))
                if edge.IsClosed():
                    points.append(points[0])
            record = {
                "id": len(result) + 1,
                "part": name,
                "kind": kind,
                "length_mm": length,
                "closed": edge.IsClosed(),
                "points": [[v.x, v.y, v.z] for v in points],
            }
            if kind == "CIRCLE":
                record["radius_mm"] = edge.radius()
            result.append(record)
    return result


def bolt_spacings(holes_flange, holes_floor, outline, first_id):
    outline = np.asarray(outline, dtype=float)
    segments = np.roll(outline, -1, axis=0) - outline
    lengths = np.linalg.norm(segments, axis=1)
    if len(holes_flange) < 3 or len(holes_flange) != len(holes_floor) or np.any(lengths == 0):
        raise ValueError("Bolt spacings need matching hole coordinates and a valid closed outline")
    cumulative = np.concatenate([[0], np.cumsum(lengths[:-1])])
    perimeter_positions = []
    for hole in holes_flange:
        fraction = np.clip(np.sum((np.asarray(hole) - outline) * segments, axis=1) / lengths**2, 0, 1)
        distance = np.linalg.norm(outline + fraction[:, None] * segments - hole, axis=1)
        nearest = int(np.argmin(distance))
        perimeter_positions.append(cumulative[nearest] + fraction[nearest] * lengths[nearest])
    order = np.argsort(perimeter_positions)
    points = np.asarray(holes_floor, dtype=float)[order]
    result = []
    for index, a in enumerate(points):
        following = (index + 1) % len(points)
        b = points[following]
        result.append({
            "id": first_id + index,
            "part": "pan",
            "kind": "BOLT_SPACING",
            "hole_ids": [index + 1, following + 1],
            "length_mm": float(np.linalg.norm(b - a)),
            "closed": False,
            "points": [a.tolist(), b.tolist()],
        })
    return result


def write_measurements(edges, output, spacings=()):
    (output / "edge_measurements.json").write_text(json.dumps({
        "units": "mm",
        "notice": "Lengths of the estimated CAD model, NOT measurements of the physical pan.",
        "edges": edges,
    }, separators=(",", ":")), encoding="utf-8")
    with (output / "edge_lengths.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["edge_id", "part", "curve_type", "length_mm", "radius_mm", "closed"])
        for edge in edges:
            writer.writerow([
                edge["id"], edge["part"], edge["kind"], f'{edge["length_mm"]:.6f}',
                f'{edge["radius_mm"]:.6f}' if "radius_mm" in edge else "", edge["closed"],
            ])
    with (output / "bolt_spacings.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["from_hole", "to_hole", "centre_to_centre_mm"])
        for spacing in spacings:
            writer.writerow([*spacing["hole_ids"], f'{spacing["length_mm"]:.6f}'])
    (output / "bolt_spacings.json").write_text(json.dumps({
        "units": "mm",
        "notice": "Straight centre-to-centre distances on the estimated flange, not verified drilling coordinates.",
        "spacings": spacings,
    }, indent=2), encoding="utf-8")


def dimensioned_previews(parts, p, edges, output, spacings=()):
    width, height = 2560, 1780
    background, foreground, accent = "#101820", "#d9e3ed", "#ffd27a"
    image = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(image)
    fonts = {
        size: ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", size)
        for size in (17, 20, 23, 28, 40)
    }
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        f'<rect width="100%" height="100%" fill="{background}"/>',
    ]

    def line(points, color=foreground, stroke=1, title=None):
        points = [tuple(point) for point in points]
        draw.line(points, fill=color, width=stroke)
        coordinates = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
        svg.append(f'<polyline points="{coordinates}" fill="none" stroke="{color}" '
                   f'stroke-width="{stroke}">')
        if title:
            svg.append(f"<title>{escape(title)}</title>")
        svg.append("</polyline>")

    def text(position, value, size=23, color=foreground, centered=False, box=False):
        x, y = position
        bounds = draw.textbbox((0, 0), value, font=fonts[size])
        text_width = bounds[2] - bounds[0]
        if centered:
            x -= text_width / 2
        if box:
            rectangle = (x - 5, y - 2, x + text_width + 5, y + size + 8)
            draw.rectangle(rectangle, fill=background)
            svg.append(f'<rect x="{rectangle[0]:.2f}" y="{rectangle[1]:.2f}" '
                       f'width="{text_width + 10}" height="{size + 10}" fill="{background}"/>')
        draw.text((x, y), value, fill=color, font=fonts[size])
        svg.append(f'<text x="{x:.2f}" y="{y + size:.2f}" font-family="Segoe UI,sans-serif" '
                   f'font-size="{size}" fill="{color}">{escape(value)}</text>')

    def dimension(a, b, offset, label):
        a, b = np.array(a), np.array(b)
        direction = (b - a) / np.linalg.norm(b - a)
        normal = np.array([-direction[1], direction[0]])
        aa, bb = a + normal * offset, b + normal * offset
        line([a, aa + normal * 8], "#63798c")
        line([b, bb + normal * 8], "#63798c")
        line([aa, bb], accent, 2)
        for point, sign in ((aa, 1), (bb, -1)):
            line([point + sign * direction * 11 + normal * 4, point,
                  point + sign * direction * 11 - normal * 4], accent, 2)
        text((aa + bb) / 2 + [0, -16], label, 20, accent, centered=True, box=True)

    def projection(points, frame):
        points = np.asarray(points)
        if frame == "flange":
            angle = math.radians(p["engine_roll_deg"])
            y = points[:, 1] * math.cos(angle) + (
                points[:, 2] - p["front_depth_mm"]
            ) * math.sin(angle)
            return np.column_stack([points[:, 0], y])
        if frame == "side":
            return points[:, [0, 2]]
        return np.column_stack([-points[:, 1], points[:, 2]])

    pan_edges = [edge for edge in edges if edge["part"] == "pan"]
    angle = math.radians(p["engine_roll_deg"])
    normal = np.array([0, -math.sin(angle), math.cos(angle)])
    center = np.array([0, 0, p["front_depth_mm"]])
    flange_edges = [
        edge for edge in pan_edges
        if np.max(np.abs((np.array(edge["points"]) - center) @ normal)) < 1e-5
    ]
    text((65, 32), "Oil pan - dimensioned inspection previews", 40)
    text((65, 95), "ALL VALUES IN mm. Estimated CAD geometry, not verified physical dimensions.", 28, accent)
    text((65, 138), "Edge labels are true 3D lengths; drawing extents are projected spans. SVG: hover any line for its edge length.", 23)

    for frame, panel, selected, title in [
        ("flange", (80, 260, 1280, 845), flange_edges, "FLANGE PLAN - viewed normal to mounting face"),
        ("side", (80, 1085, 1280, 1630), pan_edges, "SIDE - floor datum, hidden edges included"),
        ("end", (1450, 1085, 2470, 1630), pan_edges, "END - corrected lean, hidden edges included"),
    ]:
        projected = [projection(edge["points"], frame) for edge in selected]
        all_points = np.concatenate(projected)
        low, high = all_points.min(axis=0), all_points.max(axis=0)
        x0, y0, x1, y1 = panel
        scale = min((x1 - x0 - 180) / (high[0] - low[0]), (y1 - y0 - 160) / (high[1] - low[1]))
        midpoint = (low + high) / 2
        screen_center = np.array([(x0 + x1) / 2, (y0 + y1) / 2])

        def screen(points):
            return (np.asarray(points) - midpoint) * [scale, -scale] + screen_center

        text((x0, y0 - 60), title, 28)
        for edge, points in zip(selected, projected):
            label = f'E{edge["id"]} {edge["kind"]}: {edge["length_mm"]:.2f} mm'
            if "radius_mm" in edge:
                label += f'; diameter {2 * edge["radius_mm"]:.2f} mm'
            line(screen(points), "#99aebf" if frame == "flange" else "#596f80", 1, label)
        dimension(screen([low[0], low[1]]), screen([high[0], low[1]]), 48,
                  f'{high[0] - low[0]:.1f} {"flange X" if frame == "flange" else "overall span"}')
        dimension(screen([high[0], low[1]]), screen([high[0], high[1]]), 52,
                  f'{high[1] - low[1]:.1f}')
        if frame == "flange":
            for spacing in spacings:
                points = screen(projection(spacing["points"], frame))
                middle = points.mean(axis=0)
                inward = screen_center - middle
                inward /= np.linalg.norm(inward)
                a, b = spacing["hole_ids"]
                label = f'H{a}-H{b}: {spacing["length_mm"]:.2f} mm centre-to-centre'
                line(points, "#69dfed", 2, label)
                text(middle + inward * 25 + [0, -8], f'{spacing["length_mm"]:.1f}',
                     17, "#69dfed", centered=True, box=True)
                text(points[0] - inward * 18 + [0, -8], f"H{a}",
                     17, "#69dfed", centered=True, box=True)
            long_edges = sorted(
                (edge for edge in selected if edge["kind"] == "LINE"),
                key=lambda edge: edge["length_mm"], reverse=True
            )[:6]
            for edge in long_edges:
                points = screen(projection(edge["points"], frame))
                middle = points.mean(axis=0)
                outward = middle - screen_center
                outward /= np.linalg.norm(outward)
                label_point = middle + outward * 55
                line([middle, label_point], accent)
                text(label_point, f'E{edge["id"]}: {edge["length_mm"]:.1f}', 17,
                     accent, centered=True, box=True)
        else:
            line(screen([[low[0] - 12, 0], [high[0] + 12, 0]]), "#62b5cf", 2)
            if frame == "end":
                text((x0, y1 + 55), f'Flange roll: {p["engine_roll_deg"]:g} degrees; floor Z = 0', 23, accent)

    bounds = parts[0][1].val().BoundingBox()
    text((1450, 210), "IMPORTANT MODEL DIMENSIONS", 28)
    items = [
        ("Pan overall X (including bosses)", f"{bounds.xlen:.1f}"),
        ("Pan overall Y (including bosses)", f"{bounds.ylen:.1f}"),
        ("Pan overall height above floor", f"{bounds.zlen:.1f}"),
        ("Nominal flange length x width", f'{p["length_mm"]:g} x {p["flange_width_mm"]:g}'),
        ("Front floor below flange centre", f'{p["front_depth_mm"]:g}'),
        ("Rear floor below flange centre", f'{p["rear_depth_mm"]:g}'),
        ("Bridge floor below flange centre", f'{p["bridge_depth_mm"]:g}'),
        ("Bridge above ground datum", f'{p["front_depth_mm"] - p["bridge_depth_mm"]:g}'),
        ("Rear floor above ground datum", f'{p["front_depth_mm"] - p["rear_depth_mm"]:g}'),
        ("Wall / floor thickness", f'{p["wall_mm"]:g}'),
        ("Rail thickness, normal to flange", f'{p["rail_mm"]:g}'),
        ("Mounting bore diameter (estimated)", f'{p["bolt_hole_diameter_mm"]:g}'),
        ("Pickup baffle hole diameter", f'{p["baffle_pickup_hole_diameter_mm"]:g}'),
    ]
    for index, (label, value) in enumerate(items):
        y = 275 + index * 43
        text((1450, y), label, 23)
        text((2320, y), value, 23, accent)
    text((1450, 885), "Use viewer.html to click any CAD edge; Shift-click adds lengths.", 20, accent)
    text((1450, 925), "Cyan flange lines: neighbouring hole centres, distances in mm.", 20, "#69dfed")
    text((65, 1730), "Photo-derived approximation. Model precision is NOT manufacturing accuracy. No fabrication approval.", 23, accent)
    svg.append("</svg>")
    image.save(output / "dimensions.png")
    (output / "dimensions.svg").write_text("\n".join(svg), encoding="utf-8")
