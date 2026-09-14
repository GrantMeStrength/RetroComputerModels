"""Rebuild a model into build/ using the distributed construction inputs."""

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BUILDERS = {
    "WebPrototypes": "build_prototypes.py",
    "BritishModels": "build_models.py",
    "Spectrum48TS1500": "build_models.py",
}


def main():
    catalog = json.loads((ROOT / "catalog.json").read_text())
    models = {Path(m["blend"]).stem: m for m in catalog}
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model", choices=list(models))
    parser.add_argument("--blender", default=shutil.which("blender"))
    parser.add_argument("--render", action="store_true", help="Also render the builder's inspection views")
    args = parser.parse_args()
    if not args.blender:
        parser.error("Blender is not on PATH; pass --blender with its executable path")
    work = ROOT / "build"
    source = ROOT / "ModelSources"
    for path in source.rglob("*"):
        if not path.is_file() or path.suffix not in {".py", ".json", ".png", ".jpg"}:
            continue
        target = work / "ModelSources" / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    folder = Path(models[args.model]["blend"]).parent.name
    output = work / "ModelSources" / folder
    for directory in ["renders", "reports", "evidence", "Previews", "Reports"]:
        (output / directory).mkdir(exist_ok=True)
    builder = output / BUILDERS.get(folder, "build_model.py")
    options = []
    if folder in {"WebPrototypes", "BritishModels"}:
        options = ["--models", args.model]
    elif folder == "Spectrum48TS1500":
        options = [args.model]
    command = [args.blender, "--background", "--factory-startup", "--threads", "2",
               "--python-exit-code", "1", "--python", str(ROOT / "tools/run_builder.py"),
               "--", str(builder), "render" if args.render else "geometry", *options]
    subprocess.run(command, cwd=ROOT, check=True)
    print(f"Built {output.relative_to(ROOT) / (args.model + '.usdz')}")


if __name__ == "__main__":
    main()
