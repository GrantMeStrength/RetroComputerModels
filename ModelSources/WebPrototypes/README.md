# Commodore 64 and VIC-20

`commodore64` and `vic20` each include a USDZ, editable Blender scene and two
prepared artwork textures. The directory name is retained for shared imports;
superseded Apple II/Osborne experiments and comparison scenes are not included.

The 406 × 206 mm C64 enclosure uses original profile/extrusion/Boolean geometry
informed by Sgw32 NULLchar's replica enclosure, **CC BY 4.0**. The shell deck is
67 mm high; 14 mm key bodies bring the overall height to about 73.33 mm.
The key height is a visual correction, not a measurement from enclosure CAD.
The stepped keyboard and separate function-bank openings are recessed geometry.
Six rear grooves are recessed rather than painted.

The VIC-20 intentionally uses identical C64 geometry with cream/brown/tan colors
and newly drawn VIC-20 artwork. It is not an independently measured VIC-20 case,
nor a claim of motherboard/connector fit. Both omit rear/side sockets and internal
fittings; keycap sculpting, small legends and badge typography are simplified.

`reference_c64.py` contains construction profiles and dimensions. Shared geometry
helpers are in `build_prototypes.py` and `../mesh_utils.py`. `Textures/atlas.json`
provides UV regions. No third-party mesh or photograph is required by the builder.

See [build instructions](../../BUILDING.md) and
[mandatory reference attribution](../../ATTRIBUTION.md#commodore-64-and-vic-20).
