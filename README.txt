K24Z3 / MIATA OIL PAN -- PHOTO-DERIVED CAD STUDY

This is an original geometric approximation of the oil pan in the supplied
KPower product photo and Miata installation photos, not a manufacturer CAD
file. It is intended for visualization and early packaging discussion only.
DO NOT manufacture or install this model as a working oil pan.

Open exports\viewer.html in a WebGL-capable browser to orbit the model offline.
Open exports\preview.png for top/interior and underside views.
Use "End / flange tilt" for an orthographic view of the inclined rail and
horizontal bottom. The floor grid is a viewer reference, not exported geometry.
Click any visible CAD edge for its true 3D length in millimetres. Shift-click
adds/removes edges; the panel shows their sum (not the straight-line span).
Circular edges also show diameter, separately from their arc length.
Drag still orbits; rotate or use the exploded view to reach obscured edges.
The floor grid is not measurable geometry. Displayed precision is not accuracy.
Small segments around traced corners can be Shift-selected and summed.
Cyan guides join neighbouring flange bolt-hole centres, including the closing
pair around the perimeter. Their labels show true 3D centre-to-centre distances
in mm (not edge-to-edge gaps or sums along the flange contour). Click a guide
or its label for the hole IDs and precise model value. Use the "Bolt-hole
spacings" checkbox to hide them independently of CAD edges. These guides are
viewer/drawing annotations, not additional geometry in the STEP/STL exports.
Hole IDs follow perimeter order, not the image-scanner's row order.

Open exports\dimensions.png or dimensions.svg for dimensioned flange-plan,
side and end previews. The SVG has hover titles on every drawn CAD edge.
Wireframe side/end views include hidden edges. Extent arrows are projected
overall spans; edge callouts are true CAD curve lengths. Model dimensions
remain estimates of the real component, not a fabrication specification.

Files:
  exports\pan.step  - single solid, hollow pan, no removable internals/plugs
  exports\pan.stl   - the same pan, manifold mesh; coordinates in millimetres
  exports\pan_with_estimated_internals.step - named, colored CAD assembly
  exports\pan.glb   - named, colored mesh assembly; metre units
  exports\pan.obj   - mesh assembly, millimetre coordinates, vertex colors
  exports\*_estimated.stl - conceptual internals as separate solids
  exports\*_plug.stl      - unthreaded plug representations
  exports\validation.json - CAD/mesh validation and dimensional provenance
  dimensions.json        - editable parameters, millimetres/degrees
  build_model.py         - editable CadQuery construction source
  test_model.py          - flange/floor geometry regression checks
  flange_profile.json    - image-traced outer/inner contours and 16 hole centres
  trace_flange.py         - repeatable image-to-profile extraction
  exports\flange_trace.png - supplied image annotated with traces/hole centres
  measurements.py         - CAD edge measurement and drawing export
  exports\dimensions.png  - dimensioned inspection sheet
  exports\dimensions.svg  - scalable sheet with per-edge hover measurements
  exports\edge_lengths.csv - complete edge-length table in millimetres
  exports\edge_measurements.json - measured curves and sampled geometry
  exports\bolt_spacings.csv - all 16 neighbouring centre-to-centre distances
  exports\bolt_spacings.json - guide endpoints, hole IDs and distance provenance

REGENERATE (PowerShell, from this directory):
  & .\.venv\Scripts\python.exe .\build_model.py
  & .\.venv\Scripts\python.exe -m unittest -v test_model

If moving to another computer:
  python -m venv .venv
  & .\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
  & .\.venv\Scripts\python.exe .\build_model.py

KNOWN:
KPower's current product page specifies V2 .100-inch walls (2.54 mm)
and a 3/8-inch rail (9.525 mm). The reference photo version is not confirmed.
The manufacturer describes a 6-US-quart real system with baffles, two trap
doors, two drain plugs and one overflow plug. The modeled oil capacity has
NOT been calibrated to six quarts.

ENGINE ROLL CORRECTION:
ATI's K20/K24 transmission adapter announcement explicitly describes an
"OEM 15 degree slant". KPower's K24Z3 installation guide (October 2020,
revision 2) does not give a numerical engine roll angle. Page 21 shows
additional views of the pan, but the photos are not calibrated.

engine_roll_deg = -15 uses the source-backed OEM magnitude as a starting
assumption, NOT a verified KPower NA/NB mounting angle. The sign was reversed
from +15 following the user's correction: negative Y is now the high side.
The general Honda-Tech claim of approximately 13 degrees is lower-authority,
inconsistent evidence, not a measurement of this KPower installation.
No longitudinal engine pitch has been inferred.

The sump and bridge floors are now constructed on planes angled relative to
the flange, with 2.54 mm floor thickness measured vertically. Side walls retain
their flange-normal directions and are trimmed to the level floors, producing
75/105-degree floor-to-long-wall joints at the nominal roll (not all 90 degrees).
The circular mounting holes and 9.525 mm flange thickness are preserved:
neither the flange nor its holes is sheared. Baffles and drain ports follow
the revised floors. The overflow representation is on the high-rail side.
Exact side-wall and hidden baffle orientations still require measurement.

All components are then rigidly oriented with the small-well bottom at Z=0.
Simply rotating the previous model would NOT correct the flange/floor angle;
these files contain actual revised geometry, not only a viewer rotation.
At 15 degrees, a 270 mm flange has 69.9 mm height difference across its width.
The nominal small-well bottom is level at Z=0; the rear well remains 16 mm
higher from the previous estimated depths. Coplanarity of both wells has not
been established. No parts extend below the small-well floor.

REAR SUMP OUTLINE CORRECTION:
The rear reservoir is no longer a symmetric chamfered box. The underside
installation photo shows a narrower, offset throat, multi-segment shoulders,
a slightly tapered left side and a broad straight rear edge.
Following the user's symmetry correction, the bung-side shoulder now mirrors
the opposite shoulder about the throat centre. Its outer wall is inset by
30 mm in flange coordinates (about 31.1 mm in the level-floor projection).
The opposite side and throat remain fixed; the slight left rear taper remains.
rear_outline_uv in dimensions.json encodes these estimated proportions:
u runs from the bridge throat to the rear edge; v runs from photo-left
(positive Y) to photo-right (negative Y) in the front-up underside view.
The former matching chamfers at both rear corners have been removed.
The existing length and floor depths are retained. The rear_sump_width_mm
parameter is the 300 mm reference span for the normalized outline, whose
current 90-percent occupancy gives a 270 mm span in flange coordinates.
The rear drain, bore and plug move inward with the actual side wall instead
of staying on the original bounding envelope. Drain location is unverified.
The cavity, baffle and partitions are clipped to the revised outline.
The flange outline, bolt centres, front well and -15-degree roll are unchanged.
The proportions are not perspective-calibrated dimensions or a fit guarantee.
Use Bottom in the viewer: engine front is at the top, rear at the bottom,
matching the supplied installed photograph.

ESTIMATED:
456 mm nominal flange length, 270 mm nominal flange width, 300 mm rear
profile reference span (270 mm occupied), 142 mm small-well depth, 126 mm broad-well depth and 48 mm
bridge depth. The length/width are provisionally constrained by ACKOJA's
A26-0159 OEM-pattern replacement, listed as 456 x 270 x 140 mm. Both Spareto
and AUTODOC separate these part dimensions from shipping/packaging dimensions.
The part cross-references 11200-PNA-000 and 11200-RAA-A00, among others.
It is NOT a dimensioned K24Z3 mounting-plate drawing. Equating its overall
length/width with flange length/width is an unverified assumption.
The asymmetric flange, rounded corner approximations, separate inner opening
and 16 hole centres now come from the user's copilot-image-fe0fd3.png gasket
image, rather than a generic chamfered rectangle or evenly spaced pattern.
Dark-material segmentation and connected-component analysis find the aperture
centres; the outlines are simplified to within 2.5 source pixels (about 0.55 mm).
This preserves the unequal end chamfers and individual spacing. The full
contour, scaling factors and image provenance are in flange_profile.json.
X and Y use independent provisional scales differing by approximately 0.4%.
No perspective/lens calibration or gasket-to-pan variant verification was
possible, so these remain image-derived estimates, NOT machining coordinates.
The 6.8 mm bore diameter remains an assumption rather than a photo measurement.
The flange_border_mm parameter now affects the legacy body layout only; the
flange itself uses the two separate traced contours, including local pads.
The holes must NOT be used as a drilling or gasket template.
Sump shape/depth, baffles, ports, threads, pickup and sealing surfaces are not
fit-verified. Pump adapter and separate pickup assembly are not modeled.
Weld beads and exact trap-door hinges are omitted.

The common stock-K24 mounting interface is the right dimensional reference.
A K24 oil-pan/bottom-of-engine scan by Adrian Dzido was found in indexed
GrabCAD search results, but downloading it was not possible during this task.
It was not used. Its engine variant and accuracy still require confirmation.
A measured stock K24Z3 pan, flange trace or verified scan can replace the
estimated top geometry. A scan of a related K24 variant must be checked for
the relevant engine interface; similarity alone does not prove identical fit.
Moroso's published 16.75 x 9 x 5.5-inch measurements describe its aftermarket
SUMP, not the OEM mounting flange; they were deliberately not substituted.

DATUM (CHANGED FROM THE INITIAL MODEL):
Floor frame: small-well bottom Z=0, flange center Z=front_depth_mm (142 mm).
Depth parameters are vertical distances from flange center to the outer
front/rear/bridge floors, NOT distances normal to the tilted mounting face.
The flange and bolt pattern are constructed in their own XY frame (Z=0),
then rigidly rotated about X by engine_roll_deg and translated upward.
Positive Y is the high side for positive roll. Hole coordinates in both
frames are recorded in validation.json. CAD and mesh exports use floor frame.
X runs along the pan. The smaller box well is at negative X, the wider
polygonal well at positive X. Vehicle front/rear assignment is inferred.
Drain bosses/heads protrude beyond the nominal flange/sump dimensions.
GLB is scaled to metres per glTF convention; other model coordinates are mm.

TO MAKE A DIMENSIONALLY RELIABLE MODEL:
Obtain a matching stock-pan mounting outline and all bolt coordinates;
measure engine roll, longitudinal pitch, side-wall angles, flange-to-bottom
depths of both wells and the bridge, sump outlines,
drain specifications and pickup/baffle locations. Photos alone cannot confirm
sealing, subframe/rack clearance or oil control under vehicle acceleration.

SOURCES:
https://kpower.industries/products/k24z3-miata-oiling-system
https://www.reddit.com/r/Miata/comments/1266bss/kpower_k24z3_swap_post_4/
https://spareto.com/products/ackoja-oil-sump/a26-0159
https://www.autodoc.co.uk/ackojap/14480037
https://www.atiracing.com/links/pr/2025/09-Honda-K20_K24_Adapter_kit/
https://cdn.shopify.com/s/files/1/1109/4350/files/K24Z3_Installation_Guide_-_Oct_2020_revision_2.pdf?v=1603211191
https://honda-tech.com/forums/k-series-153/dry-sump-mounting-angles-3344844/
https://grabcad.com/library/k24-oil-pan-oil-pickup-baffles-1/files
https://www.realstreetperformance.com/moroso-oil-pan-steel-race-baffled-for-k20-k24-engine-swaps-integra-da-dc-ef-eg.html
