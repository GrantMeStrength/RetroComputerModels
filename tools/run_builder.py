"""Blender entry point used by rebuild.py."""

from pathlib import Path
import os
import runpy
import sys

import bpy

arguments = sys.argv[sys.argv.index("--") + 1:]
builder, mode, *options = arguments
bpy.context.preferences.filepaths.save_version = 0
sys.argv = [str(Path(builder)), "--", *options]
os.environ["RETRO_RENDER"] = "1" if mode == "render" else "0"
runpy.run_path(builder, run_name="__main__")
