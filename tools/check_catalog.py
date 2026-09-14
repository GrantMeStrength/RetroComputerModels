"""Check catalog assets, checksums, embedded archive members and size limits."""

import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
catalog = json.loads((ROOT / "catalog.json").read_text())
assert len({m["name"] for m in catalog}) == len(catalog), "Duplicate model names"
for field, extension, folder in [("blend", ".blend", "ModelSources"),
                                  ("usdz", ".usdz", "ModelSources"),
                                  ("preview", ".png", "previews")]:
    listed = {m[field] for m in catalog}
    actual = {p.relative_to(ROOT).as_posix() for p in (ROOT / folder).rglob("*" + extension)}
    assert listed == actual, f"Catalog mismatch for {extension}: {listed ^ actual}"
    for model in catalog:
        path = ROOT / model[field]
        assert path.stat().st_size < 100_000_000, f"GitHub file limit: {path}"
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        assert checksum == model[field + "_sha256"], f"Checksum mismatch: {path}"
for model in catalog:
    with zipfile.ZipFile(ROOT / model["usdz"]) as archive:
        assert archive.testzip() is None, model["usdz"]
        for name in archive.namelist():
            assert not name.startswith("/") and ".." not in Path(name).parts, name
            assert Path(name).suffix.lower() not in {".exr", ".stl", ".3mf", ".blend"}, name
print(f"PASS: {len(catalog)} Blender scenes, {len(catalog)} USDZ archives, {len(catalog)} previews")
