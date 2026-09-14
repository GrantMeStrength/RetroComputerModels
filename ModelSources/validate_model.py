"""Check exported case geometry and embedded USDZ dependencies."""

from collections import Counter
import json
from pathlib import Path
import struct
import sys
import zipfile

from pxr import Sdf, Usd, UsdGeom, UsdValidation


def validate(path):
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        with path.open("rb") as stream:
            for member in archive.infolist():
                if member.compress_type != zipfile.ZIP_STORED:
                    raise ValueError(f"Compressed USDZ member: {member.filename}")
                stream.seek(member.header_offset + 26)
                name_size, extra_size = struct.unpack("<HH", stream.read(4))
                if (member.header_offset + 30 + name_size + extra_size) % 64:
                    raise ValueError(f"Unaligned USDZ member: {member.filename}")
    stage = Usd.Stage.Open(str(path))
    if UsdGeom.GetStageUpAxis(stage) != "Y":
        raise ValueError("Model must be Y-up for the app")
    result = {"file": path.name, "bytes": path.stat().st_size, "meshes": []}
    for prim in stage.Traverse():
        if prim.IsA(UsdGeom.Mesh):
            mesh = UsdGeom.Mesh(prim)
            points = mesh.GetPointsAttr().Get()
            indices = mesh.GetFaceVertexIndicesAttr().Get()
            counts = mesh.GetFaceVertexCountsAttr().Get()
            edges = Counter()
            oriented = Counter()
            seen = set()
            offset = 0
            for count in counts:
                face = list(indices[offset:offset + count])
                offset += count
                if count != 3 or len(set(face)) != count:
                    raise ValueError(f"Invalid triangle: {prim.GetPath()}")
                if min(face) < 0 or max(face) >= len(points):
                    raise ValueError("Out-of-range vertex index")
                a, b, c = [points[i] for i in face]
                if ((b - a) ^ (c - a)).GetLength() < 1e-12:
                    raise ValueError("Degenerate triangle")
                key = tuple(sorted(face))
                if key in seen:
                    raise ValueError("Duplicate face")
                seen.add(key)
                for a, b in zip(face, face[1:] + face[:1]):
                    edges[tuple(sorted((a, b)))] += 1
                    oriented[(a, b)] += 1
            if any(n != 2 for n in edges.values()):
                raise ValueError(f"Open/non-manifold mesh: {prim.GetPath()}")
            if any(oriented[(a, b)] != oriented[(b, a)] for a, b in edges):
                raise ValueError("Inconsistent face orientation")
            uv = UsdGeom.PrimvarsAPI(prim).GetPrimvar("st")
            if not uv or len(uv.ComputeFlattened()) != len(indices):
                raise ValueError("Missing per-corner UVs")
            result["meshes"].append({"vertices": len(points), "triangles": len(counts)})
        if prim.GetTypeName().endswith("Light") or prim.IsA(UsdGeom.Camera):
            raise ValueError("Unexpected scene lighting/camera in asset")
        for attribute in prim.GetAttributes():
            if attribute.GetTypeName() == Sdf.ValueTypeNames.Asset:
                asset = attribute.Get()
                if asset and asset.path.removeprefix("./") not in names:
                    raise ValueError(f"Missing embedded asset: {asset}")
    registry = UsdValidation.ValidationRegistry()
    context = UsdValidation.ValidationContext(registry.GetOrLoadAllValidators())
    errors = context.Validate(stage)
    issues = [error.GetMessage() for error in errors if error.GetType() == UsdValidation.ValidationErrorType.Error]
    if issues:
        raise ValueError("\n".join(issues))
    result["warnings"] = [error.GetMessage() for error in errors if error.GetType() == UsdValidation.ValidationErrorType.Warn]
    if not result["meshes"]:
        raise ValueError("No mesh in export")
    return result


if __name__ == "__main__":
    for name in sys.argv[1:]:
        print(json.dumps(validate(Path(name)), indent=2))
