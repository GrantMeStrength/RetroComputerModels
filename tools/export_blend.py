"""Export the visible model geometry, excluding named preview studio aids.

blender --background --factory-startup --python tools/export_blend.py -- input.blend output.usdz
"""

from pathlib import Path
import sys

import bpy

args = sys.argv[sys.argv.index("--") + 1:]
if len(args) != 2:
    raise ValueError("Expected input.blend and output.usdz")
source, destination = [Path(p).resolve() for p in args]
if source.suffix != ".blend" or destination.suffix != ".usdz":
    raise ValueError("Expected .blend input and .usdz output")
if destination.exists():
    raise FileExistsError("Choose a new output path; existing files are not overwritten")
destination.parent.mkdir(parents=True, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=str(source))
bpy.ops.object.select_all(action="DESELECT")
selected = []
for obj in bpy.context.scene.objects:
    name = obj.name.lower()
    studio = any("preview" in c.name.lower() or "studio" in c.name.lower() for c in obj.users_collection)
    if obj.type == "MESH" and not studio and not name.startswith(("preview", "reviewonly", "studio ground")):
        obj.select_set(True)
        selected.append(obj)
if not selected:
    raise ValueError("No model meshes found")
bpy.context.view_layer.objects.active = selected[0]
bpy.ops.wm.usd_export(
    filepath=str(destination), selected_objects_only=True,
    export_materials=True, generate_preview_surface=True,
    convert_orientation=True, export_global_up_selection="Y",
    export_global_forward_selection="NEGATIVE_Z", convert_world_material=False,
    export_lights=False, export_cameras=False, export_custom_properties=False,
    triangulate_meshes=True, overwrite_textures=True,
)
