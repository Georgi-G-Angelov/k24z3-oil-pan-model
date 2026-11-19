"""Photo-derived KPower-style pan study. Dimensions are mm, not fit-certified."""

import argparse
import json
import math
from pathlib import Path

import cadquery as cq
import numpy as np
import trimesh
from OCP.BRepAdaptor import BRepAdaptor_Surface
from PIL import Image, ImageDraw, ImageFont
from measurements import bolt_spacings, dimensioned_previews, extract_edges, write_measurements

ROOT = Path(__file__).resolve().parent


def prism(points, bottom, top, inset=0):
    sketch = cq.Workplane("XY").workplane(offset=bottom).polyline(points).close()
    if inset:
        sketch = sketch.wires().offset2D(-inset)
    return sketch.extrude(top - bottom)


def box(x, y, z, dx, dy, dz):
    return cq.Workplane("XY").box(dx, dy, dz).translate((x, y, z))


def axial_circle(plane, origin, radius, length):
    return cq.Workplane(plane, origin=origin).circle(radius).extrude(length)


def floor_frame(point, p):
    x, y, z = point
    angle = math.radians(p["engine_roll_deg"])
    return (
        x, y * math.cos(angle) - z * math.sin(angle),
        p["front_depth_mm"] + y * math.sin(angle) + z * math.cos(angle),
    )


def flange_z_at_level(level, y, p):
    angle = math.radians(p["engine_roll_deg"])
    return (level - y * math.sin(angle)) / math.cos(angle)


def level_halfspace(level, p, above=True):
    angle = math.radians(p["engine_roll_deg"])
    size = 4 * max(p["length_mm"], p["front_depth_mm"], p["rear_depth_mm"])
    plane = cq.Plane(
        origin=(0, 0, flange_z_at_level(level, 0, p)),
        xDir=(1, 0, 0), normal=(0, math.sin(angle), math.cos(angle)),
    )
    return cq.Workplane(plane).rect(size, size).extrude(size if above else -size)


def flange_profile(p):
    profile = json.loads((ROOT / "flange_profile.json").read_text(encoding="utf-8"))
    scale = np.array([
        p["length_mm"] / profile["reference_length_mm"],
        p["flange_width_mm"] / profile["reference_width_mm"],
    ])
    return {
        key: (np.array(profile[key]) * scale).tolist()
        for key in ("outer_mm", "inner_mm", "bolt_centers_mm")
    }


def outline_edge_y(x, points, side=1):
    intersections = [
        a[1] + (b[1] - a[1]) * (x - a[0]) / (b[0] - a[0])
        for a, b in zip(points, points[1:] + points[:1])
        if min(a[0], b[0]) <= x < max(a[0], b[0])
    ]
    if not intersections:
        raise ValueError(f"No outline edge at X={x}")
    return max(intersections) if side > 0 else min(intersections)


def inner_edge_y(x, p, side=1):
    return outline_edge_y(x, flange_profile(p)["inner_mm"], side)


def rear_sump_outline(p):
    uv = np.asarray(p["rear_outline_uv"], dtype=float)
    if (
        uv.ndim != 2 or uv.shape[1] != 2 or len(uv) < 3
        or not np.isfinite(uv).all() or np.any(uv < 0) or np.any(uv > 1)
    ):
        raise ValueError("Rear outline must contain finite (u, v) pairs between 0 and 1")
    start = p["length_mm"] / 2 - p["rear_well_length_mm"] - 5
    end = p["length_mm"] / 2 - 8
    return [
        (start + u * (end - start), (0.5 - v) * p["rear_sump_width_mm"])
        for u, v in uv
    ]


def make_parts(p):
    length = p["length_mm"]
    width = p["flange_width_mm"]
    wall = p["wall_mm"]
    rail = p["rail_mm"]
    border = p["flange_border_mm"]
    bridge = p["bridge_depth_mm"]
    front_depth = p["front_depth_mm"]
    rear_depth = p["rear_depth_mm"]
    half_l, half_w = length / 2, width / 2
    rear_start = half_l - p["rear_well_length_mm"] - 5
    front_end = -half_l + border + p["front_well_length_mm"]
    rear_w = p["rear_sump_width_mm"] / 2
    angle = math.radians(p["engine_roll_deg"])

    if not (
        length > 350 and width > 180 and 0 < wall < rail < bridge
        and bridge < min(front_depth, rear_depth)
        and border > wall + p["bolt_hole_diameter_mm"]
        and rear_start - front_end > 70
        and rear_w >= half_w
        and rear_start < half_l - 125
        and math.isfinite(angle) and abs(p["engine_roll_deg"]) <= 18
        and bridge > half_w * abs(math.sin(angle)) + rail * math.cos(angle) + wall
    ):
        raise ValueError("Dimensions do not support this pan topology.")

    profile = flange_profile(p)
    outline = profile["outer_mm"]
    inner = profile["inner_mm"]
    hole_centers = profile["bolt_centers_mm"]
    rear = rear_sump_outline(p)
    lower_bound = -2 * max(front_depth, rear_depth, width)
    opening_column = prism(inner, lower_bound, 1)
    opening = opening_column.intersect(level_halfspace(-bridge + wall, p))
    flange = prism(outline, -rail, 0).cut(opening_column)
    upper_column = prism(inner, lower_bound, 1, -wall)
    upper = prism(inner, lower_bound, -rail, -wall).intersect(
        level_halfspace(-bridge, p)
    )
    front_limit = box(
        (front_end - half_l - 20) / 2, 0, (lower_bound + 1) / 2,
        front_end + half_l + 20, width * 3, 1 - lower_bound,
    )
    front_inner_limit = front_limit.translate((-wall, 0, 0))
    well_top = level_halfspace(-bridge + wall, p, above=False)
    front_outer = upper_column.intersect(front_limit).intersect(
        level_halfspace(-front_depth, p)
    ).intersect(well_top)
    rear_outer = prism(rear, lower_bound, 1).intersect(
        level_halfspace(-rear_depth, p)
    ).intersect(well_top)
    rear_void = prism(rear, lower_bound, 1, wall).intersect(
        level_halfspace(-rear_depth + wall, p)
    ).intersect(level_halfspace(-bridge, p, above=False))
    rear_passage = prism(rear, lower_bound, 1, wall).intersect(
        opening_column
    ).intersect(level_halfspace(-bridge - 1, p))
    front_void = opening_column.intersect(front_inner_limit).intersect(
        level_halfspace(-front_depth + wall, p)
    )
    pan = flange.union(upper).union(front_outer).union(rear_outer)
    pan = pan.cut(opening).cut(front_void).cut(rear_void).cut(rear_passage)

    holes = (
        cq.Workplane("XY").workplane(offset=-rail - 1)
        .pushPoints(hole_centers).circle(p["bolt_hole_diameter_mm"] / 2)
        .extrude(rail + 2)
    )
    pan = pan.cut(holes)

    drain_radius = p["drain_bore_diameter_mm"] / 2
    front_z = flange_z_at_level(-front_depth + 25, 0, p)
    # Follow the revised wall instead of the nominal rear-width envelope.
    rear_x = rear_start + 0.84 * (half_l - 8 - rear_start)
    rear_y = outline_edge_y(rear_x, rear, side=-1)
    rear_z = flange_z_at_level(-rear_depth + 21, rear_y, p)
    front_boss = axial_circle(
        "YZ", (-half_l + border - 12, 0, front_z), 12, 15
    )
    rear_boss = axial_circle(
        "XZ", (rear_x, rear_y + 3, rear_z), 12, 15
    )
    pan = pan.union(front_boss).union(rear_boss)
    pan = pan.cut(axial_circle(
        "YZ", (-half_l + border - 14, 0, front_z), drain_radius, 22
    ))
    pan = pan.cut(axial_circle(
        "XZ", (rear_x, rear_y + 7, rear_z), drain_radius, 24
    ))

    overflow_x = rear_start + 20
    overflow_side = 1 if angle >= 0 else -1
    overflow_y = inner_edge_y(overflow_x, p, overflow_side) + overflow_side * wall
    overflow_z = flange_z_at_level(-bridge + 10, overflow_y, p)
    pan = pan.union(axial_circle(
        "XZ", (overflow_x, overflow_y - overflow_side * 2, overflow_z),
        10, -overflow_side * 12
    ))
    pan = pan.cut(axial_circle(
        "XZ", (overflow_x, overflow_y - overflow_side * 6, overflow_z),
        5, -overflow_side * 20
    ))
    pan = pan.clean()

    def plug(plane, origin, radius, head_width, shaft_length, outward=1):
        shaft = cq.Workplane(plane, origin=origin).circle(radius - 0.25).extrude(
            -outward * shaft_length
        )
        head = cq.Workplane(plane, origin=origin).polygon(6, head_width).extrude(
            outward * 6
        )
        return head.union(shaft)

    parts = [
        ("pan", pan, (0.73, 0.77, 0.81)),
        ("front_drain_plug", plug(
            "YZ", (-half_l + border - 12, 0, front_z),
            drain_radius, 21, 12, outward=-1
        ), (0.32, 0.43, 0.53)),
        ("rear_drain_plug", plug(
            "XZ", (rear_x, rear_y - 12, rear_z), drain_radius, 21, 12
        ), (0.32, 0.43, 0.53)),
        ("overflow_plug", plug(
            "XZ", (overflow_x, overflow_y + overflow_side * 10, overflow_z),
            5, 16, 10, outward=-overflow_side
        ), (0.32, 0.43, 0.53)),
    ]
    baffle_z = -p["baffle_depth_mm"]
    plate = prism(rear, baffle_z - wall, baffle_z, wall + 1).intersect(
        prism(inner, baffle_z - wall, baffle_z, 1)
    )
    pickup_x = half_l - 81
    plate = plate.cut(axial_circle(
        "XY", (pickup_x, 0, baffle_z - wall - 1),
        p["baffle_pickup_hole_diameter_mm"] / 2, wall + 2
    ))
    plate = plate.cut(
        cq.Workplane("XY").workplane(offset=baffle_z - wall - 1)
        .pushPoints([(pickup_x - 45, -65), (pickup_x - 45, 65)])
        .circle(3.2).extrude(wall + 2)
    )
    parts.append(("pickup_baffle_estimated", plate, (0.62, 0.67, 0.70)))

    # Hidden partitions/doors are concepts, not recovered manufacturer geometry.
    high_z = baffle_z - wall - 1
    for sign, suffix in [(-1, "left"), (1, "right")]:
        y = sign * 54
        partition = prism([
            (pickup_x - 53, y - wall / 2), (pickup_x + 53, y - wall / 2),
            (pickup_x + 53, y + wall / 2), (pickup_x - 53, y + wall / 2),
        ], lower_bound, high_z).intersect(
            level_halfspace(-rear_depth + wall + 1, p)
        )
        window_z = flange_z_at_level(-rear_depth + wall + 26, y, p)
        partition = partition.cut(box(pickup_x, y, window_z, 42, wall + 2, 38))
        door = box(pickup_x, y - sign * (wall + 1), window_z, 46, 1.5, 42)
        parts.append((f"partition_{suffix}_estimated", partition, (0.59, 0.64, 0.68)))
        parts.append((f"trap_door_{suffix}_estimated", door, (0.37, 0.43, 0.48)))

    for offset in (33, 79):
        x = -half_l + border + offset
        rib_half_width = half_w - border - wall - 1
        rib = prism([
            (x - wall / 2, -rib_half_width), (x + wall / 2, -rib_half_width),
            (x + wall / 2, rib_half_width), (x - wall / 2, rib_half_width),
        ], lower_bound, -rail - 5).intersect(
            level_halfspace(-front_depth + wall, p)
        )
        rib = rib.cut(box(
            x, 0, flange_z_at_level(-front_depth + wall + 28, 0, p),
            wall + 2, 58, 52
        ))
        parts.append((f"front_rib_{offset}_estimated", rib, (0.64, 0.69, 0.73)))
    interior = opening.union(front_void).union(rear_void).union(rear_passage)
    parts = [
        (name, part.intersect(interior).clean() if "estimated" in name else part, color)
        for name, part, color in parts
    ]
    parts = [
        (name, part.rotate((0, 0, 0), (1, 0, 0), p["engine_roll_deg"])
         .translate((0, 0, front_depth)), color)
        for name, part, color in parts
    ]
    return parts, hole_centers, outline


def validate_parts(parts, output):
    reports = {}
    meshes = []
    for name, part, color in parts:
        shape = part.val()
        if not shape.isValid() or len(shape.Solids()) != 1 or shape.Volume() <= 0:
            raise ValueError(f"{name}: invalid or disconnected CAD solid")
        cq.exporters.export(
            part, str(output / f"{name}.stl"), tolerance=0.15, angularTolerance=0.15
        )
        mesh = trimesh.load_mesh(output / f"{name}.stl", process=True)
        if not mesh.is_watertight or not mesh.is_volume or mesh.body_count != 1:
            raise ValueError(f"{name}: exported mesh failed manifold checks")
        reports[name] = {
            "cad_valid": True,
            "cad_solids": 1,
            "mesh_watertight": bool(mesh.is_watertight),
            "mesh_winding_consistent": bool(mesh.is_winding_consistent),
            "mesh_components": mesh.body_count,
            "triangles": len(mesh.faces),
            "bounds_mm": mesh.bounds.tolist(),
            "material_volume_mm3": shape.Volume(),
        }
        meshes.append((name, mesh, color))
    return reports, meshes


def validate_features(pan, p, holes):
    solid = pan.val().Solids()[0]
    wall = p["wall_mm"]
    front_x = -p["length_mm"] / 2 + p["flange_border_mm"] + 65
    rear_x = p["length_mm"] / 2 - 81
    wall_y = inner_edge_y(0, p) + wall / 2
    wall_z = (-p["rail_mm"] + flange_z_at_level(-p["bridge_depth_mm"], wall_y, p)) / 2
    checks = {
        "open_bridge_cavity": ((0, 0, -20), False),
        "rack_clearance_below_bridge": ((0, 0, -100), False),
        "bridge_floor_present": (
            (0, 0, flange_z_at_level(-p["bridge_depth_mm"] + wall / 2, 0, p)), True
        ),
        "front_well_hollow": ((front_x, 0, -100), False),
        "front_floor_present": (
            (front_x, 0, flange_z_at_level(-p["front_depth_mm"] + wall / 2, 0, p)), True
        ),
        "rear_well_hollow": ((rear_x, 0, -100), False),
        "rear_floor_present": (
            (rear_x, 0, flange_z_at_level(-p["rear_depth_mm"] + wall / 2, 0, p)), True
        ),
        "upper_side_wall_present": (
            (0, wall_y, wall_z),
            True,
        ),
    }
    for name, (point, expected_inside) in checks.items():
        if solid.isInside(cq.Vector(*floor_frame(point, p)), 1e-6) != expected_inside:
            raise ValueError(f"Pan geometry feature failed: {name}")
    for x, y in holes:
        point = floor_frame((x, y, -p["rail_mm"] / 2), p)
        if solid.isInside(cq.Vector(*point), 1e-6):
            raise ValueError("A flange bolt hole is blocked")
    return {name: True for name in checks} | {"all_flange_holes_open": True}


def validate_floor_geometry(pan, p, hole_count):
    shape = pan.val()
    normal = cq.Vector(
        0, -math.sin(math.radians(p["engine_roll_deg"])),
        math.cos(math.radians(p["engine_roll_deg"])),
    )
    center = cq.Vector(0, 0, p["front_depth_mm"])
    planar_faces = [face for face in shape.Faces() if face.geomType() == "PLANE"]
    flange_faces = [
        face for face in planar_faces
        if (face.normalAt() - normal).Length < 1e-6
        and abs((face.Center() - center).dot(normal)) < 1e-6
        and face.Area() > 1000
    ]
    if not flange_faces:
        raise ValueError("No mounting face on the specified tilted flange plane")
    measured_angle = math.degrees(math.acos(max(-1, min(1, flange_faces[0].normalAt().z))))
    measured_normal = flange_faces[0].normalAt()
    measured_roll = math.degrees(math.atan2(-measured_normal.y, measured_normal.z))
    if not math.isclose(measured_angle, abs(p["engine_roll_deg"]), abs_tol=1e-6):
        raise ValueError("Actual flange-to-floor angle differs from the parameter")
    if not math.isclose(measured_roll, p["engine_roll_deg"], abs_tol=1e-6):
        raise ValueError("Actual flange lean direction differs from the parameter")
    floor_levels = [
        0, p["front_depth_mm"] - p["rear_depth_mm"],
        p["front_depth_mm"] - p["bridge_depth_mm"],
    ]
    for level in floor_levels:
        for offset, direction in [(0, -1), (p["wall_mm"], 1)]:
            if not any(
                abs(face.Center().z - level - offset) < 1e-6
                and abs(face.normalAt().z - direction) < 1e-6
                and face.Area() > 100
                for face in planar_faces
            ):
                raise ValueError(f"Missing level floor surface at Z={level + offset}")
    if abs(shape.BoundingBox().zmin) > 1e-6:
        raise ValueError("Pan must rest on its small-well bottom at Z=0")
    bolt_surfaces = []
    actual_hole_axes = []
    for face in shape.Faces():
        if face.geomType() != "CYLINDER":
            continue
        cylinder = BRepAdaptor_Surface(face.wrapped).Cylinder()
        if math.isclose(cylinder.Radius(), p["bolt_hole_diameter_mm"] / 2, abs_tol=1e-6):
            axis = cylinder.Axis().Direction()
            if abs(abs(cq.Vector(axis.X(), axis.Y(), axis.Z()).dot(normal)) - 1) > 1e-6:
                raise ValueError("A mounting bore is not normal to the flange")
            bolt_surfaces.append(face)
            location = cylinder.Axis().Location()
            actual_hole_axes.append(cq.Vector(location.X(), location.Y(), location.Z()))
    if len(bolt_surfaces) != hole_count:
        raise ValueError("Mounting holes were distorted or lost")
    for x, y in flange_profile(p)["bolt_centers_mm"]:
        expected = cq.Vector(*floor_frame((x, y, 0), p))
        if not any((expected - location).cross(normal).Length < 1e-5
                   for location in actual_hole_axes):
            raise ValueError("A mounting bore does not match the traced image position")
    for face in bolt_surfaces:
        depths = [(vertex.Center() - center).dot(normal) for vertex in face.Vertices()]
        if not math.isclose(max(depths) - min(depths), p["rail_mm"], abs_tol=1e-6):
            raise ValueError("Flange thickness changed along a mounting hole")
    return {
        "measured_flange_to_floor_deg": measured_angle,
        "measured_signed_roll_deg": measured_roll,
        "horizontal_outer_floor_levels_mm": floor_levels,
        "floor_thickness_mm": p["wall_mm"],
        "circular_flange_normal_bores": len(bolt_surfaces),
        "all_bore_axes_match_image_trace": True,
        "flange_normal_thickness_mm": p["rail_mm"],
        "pan_min_z_mm": shape.BoundingBox().zmin,
    }


def preview(meshes, p, output):
    image = Image.new("RGB", (1600, 1050), "#101820")
    draw = ImageDraw.Draw(image)
    font_path = Path(r"C:\Windows\Fonts\segoeui.ttf")
    font = ImageFont.truetype(str(font_path), 22)
    title = ImageFont.truetype(str(font_path), 36)
    draw.text((50, 30), "K24Z3 / Miata oil-pan shape study", font=title, fill="#edf3fa")
    draw.text((50, 85), "PHOTO-DERIVED APPROXIMATION  |  NOT A VERIFIED FIT OR FABRICATION DRAWING",
              font=font, fill="#eabe7f")
    pixels = np.array(image)
    for center, yaw, tilt, label, names in [
        ((785, 370), -0.50, -0.94, "Top / interior", None),
        ((785, 800), 0.50, 2.10, "Underside / rack-clearance bridge", {"pan"}),
    ]:
        cz, sz = math.cos(yaw), math.sin(yaw)
        cx, sx = math.cos(tilt), math.sin(tilt)
        rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
        rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
        rotation = rx @ rz
        selected = [(name, mesh, color) for name, mesh, color in meshes
                    if names is None or name in names]
        projected = np.concatenate([
            (mesh.vertices - [0, 0, p["front_depth_mm"] / 2]) @ rotation.T
            for _, mesh, _ in selected
        ])
        span = np.ptp(projected[:, :2], axis=0)
        scale = min(1320 / span[0], 340 / span[1])
        midpoint = (projected[:, :2].max(axis=0) + projected[:, :2].min(axis=0)) / 2
        depth_buffer = np.full((image.height, image.width), -np.inf)
        light = np.array([-0.35, -0.25, 0.90])
        for name, mesh, color in selected:
            vertices = (mesh.vertices - [0, 0, p["front_depth_mm"] / 2]) @ rotation.T
            normals = mesh.face_normals @ rotation.T
            for tri, normal in zip(vertices[mesh.faces], normals):
                brightness = 0.43 + 0.57 * max(0, np.dot(normal, light))
                rgb = tuple(int(min(255, c * 255 * brightness)) for c in color)
                xy = (tri[:, :2] - midpoint) * [scale, -scale] + center
                x0 = max(0, math.floor(xy[:, 0].min()))
                x1 = min(image.width - 1, math.ceil(xy[:, 0].max()))
                y0 = max(0, math.floor(xy[:, 1].min()))
                y1 = min(image.height - 1, math.ceil(xy[:, 1].max()))
                if x1 < x0 or y1 < y0:
                    continue
                a, b, c = xy
                denominator = ((b[1] - c[1]) * (a[0] - c[0])
                               + (c[0] - b[0]) * (a[1] - c[1]))
                if abs(denominator) < 1e-10:
                    continue
                xx, yy = np.meshgrid(
                    np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5
                )
                w0 = ((b[1] - c[1]) * (xx - c[0])
                      + (c[0] - b[0]) * (yy - c[1])) / denominator
                w1 = ((c[1] - a[1]) * (xx - c[0])
                      + (a[0] - c[0]) * (yy - c[1])) / denominator
                w2 = 1 - w0 - w1
                depth = w0 * tri[0, 2] + w1 * tri[1, 2] + w2 * tri[2, 2]
                previous = depth_buffer[y0:y1 + 1, x0:x1 + 1]
                visible = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6) & (depth > previous)
                pixels[y0:y1 + 1, x0:x1 + 1][visible] = rgb
                previous[visible] = depth[visible]
    image = Image.fromarray(pixels)
    draw = ImageDraw.Draw(image)
    draw.text((55, 170), "Top / interior", font=font, fill="#a3b4c5")
    draw.text((55, 600), "Underside / rack-clearance bridge", font=font, fill="#a3b4c5")
    draw.text((50, 1002), "Units: mm. Flange pattern, sump dimensions and hidden baffles are estimates.",
              font=font, fill="#eabe7f")
    image.save(output / "preview.png")


def write_viewer(meshes, p, output, edges, spacings):
    payload = []
    for name, mesh, color in meshes:
        payload.append({
            "name": name, "color": color,
            "positions": np.round(mesh.triangles.reshape(-1), 4).tolist(),
            "normals": np.round(np.repeat(mesh.face_normals, 3, axis=0).reshape(-1), 5).tolist(),
        })
    template = (ROOT / "viewer_template.html").read_text(encoding="utf-8")
    dimensions = json.dumps({k: v for k, v in p.items() if not k.startswith("_")}, indent=2)
    template = template.replace("__MESH_DATA__", json.dumps(payload, separators=(",", ":")))
    template = template.replace("__EDGE_DATA__", json.dumps(edges, separators=(",", ":")))
    template = template.replace("__BOLT_SPACING_DATA__", json.dumps(spacings, separators=(",", ":")))
    template = template.replace("__DIMENSIONS__", dimensions)
    template = template.replace("__ROLL_DEG__", f'{p["engine_roll_deg"]:g}')
    template = template.replace("__CENTER_Z__", str(p["front_depth_mm"] / 2))
    template = template.replace(
        "__FLANGE_RISE__", f'{p["flange_width_mm"] * math.sin(math.radians(p["engine_roll_deg"])):.1f}'
    )
    (output / "viewer.html").write_text(template, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dimensions", type=Path, default=ROOT / "dimensions.json")
    parser.add_argument("--output", type=Path, default=ROOT / "exports")
    args = parser.parse_args()
    p = json.loads(args.dimensions.read_text(encoding="utf-8"))
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    parts, holes, outline = make_parts(p)
    feature_checks = validate_features(parts[0][1], p, holes)
    floor_checks = validate_floor_geometry(parts[0][1], p, len(holes))
    reports, meshes = validate_parts(parts, output)
    cq.exporters.export(parts[0][1], str(output / "pan.step"))
    imported = cq.importers.importStep(str(output / "pan.step")).val()
    if not imported.isValid() or len(imported.Solids()) != 1:
        raise ValueError("STEP round-trip failed")
    if not math.isclose(imported.Volume(), parts[0][1].val().Volume(), rel_tol=1e-8):
        raise ValueError("STEP round-trip changed the solid volume")
    assembly = cq.Assembly(name="photo_derived_oil_pan_NOT_FIT_CERTIFIED")
    for name, part, color in parts:
        assembly.add(part, name=name, color=cq.Color(*color))
    assembly.export(str(output / "pan_with_estimated_internals.step"))
    scene = trimesh.Scene()
    for name, mesh, color in meshes:
        visual_mesh = mesh.copy()
        visual_mesh.visual.face_colors = [round(c * 255) for c in color] + [255]
        scene.add_geometry(visual_mesh, node_name=name, geom_name=name)
    metre_scene = scene.copy()
    metre_scene.apply_scale(0.001)
    metre_scene.export(str(output / "pan.glb"))
    scene.export(str(output / "pan.obj"))
    preview(meshes, p, output)
    edges = extract_edges(parts)
    spacings = bolt_spacings(
        holes, [floor_frame((x, y, 0), p) for x, y in holes], outline, len(edges) + 1
    )
    write_measurements(edges, output, spacings)
    dimensioned_previews(parts, p, edges, output, spacings)
    write_viewer(meshes, p, output, edges, spacings)
    (output / "validation.json").write_text(json.dumps({
        "units": "mm",
        "step_round_trip_valid": True,
        "pan_feature_checks": feature_checks,
        "floor_geometry_checks": floor_checks,
        "parts": reports,
        "coordinate_frame": "Floor frame: small-well bottom Z=0; flange center at front_depth_mm.",
        "estimated_bolt_centers_flange_frame_mm": holes,
        "estimated_bolt_centers_floor_frame_mm": [
            floor_frame((x, y, 0), p) for x, y in holes
        ],
        "estimated_flange_outline_flange_frame_mm": outline,
        "estimated_rear_sump_outline_flange_frame_mm": rear_sump_outline(p),
        "provenance": p["_provenance"],
    }, indent=2), encoding="utf-8")
    print(f"Exported {len(parts)} valid solids to {output}")
    print(f"Pan: {reports['pan']['triangles']} triangles, watertight; STEP round-trip valid.")


if __name__ == "__main__":
    main()
