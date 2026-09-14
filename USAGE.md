# Using, editing and exporting

## View a model

Download a catalog `.usdz` using GitHub's **Download raw file** button. Open it
in Quick Look or another compatible viewer. Model geometry and textures are
embedded; no separate source photograph, decal or texture download is needed.

## Edit a packed Blender scene

Open its `.blend` in Blender (**5.2.1 LTS** was used for verification).
Geometry, materials and all necessary image textures are inside the file.
No original supplied photos, decals, CAD/STLs or raw-reference archives are
distributed as separate files. Construction/research pipelines are not included:
the editable Blender scenes, not a raw-reference rebuild, are the source deliverable.

Use Edit Mode to change meshes and the Material/Image Editors to adjust
materials or packed artwork. For external image editing, use Blender's
**File → External Data → Unpack Resources** into your own working directory.
After editing, use **Pack Resources** and save a new scene copy. Keep image
dimensions/aspect ratios and UV mapping unchanged unless intentionally changing
the appearance. Original photographic lighting and wear may remain in textures.
Retain the [credits and rights notices](ATTRIBUTION.md) when sharing derivatives.

Some scenes join components into one mesh with multiple materials. Preview
cameras, lights and grounds may remain for convenience; those are not model parts.
The original construction geometry/artwork was preserved during publication.
The packed scenes were opened and checked with no external texture files available.

## Export an edited scene

With `blender` on PATH, run from the repository root and choose a **new** output:

```sh
blender --background --factory-startup --python-exit-code 1 \
  --python tools/export_blend.py -- \
  ModelSources/AppleIIReferenceRebuild/appleIIe.blend build/exports/appleIIe.usdz
```

On macOS, a common executable path is
`/Applications/Blender.app/Contents/MacOS/Blender`.
The helper runs headlessly, selects model meshes, excludes named preview/review
studio aids, and exports embedded materials/textures in metres with Y up.
It omits cameras, lights, world environments and custom properties, and refuses
to overwrite an existing output. Name any added studio objects with a `Preview`
or `ReviewOnly` prefix, or place them in a preview/studio collection.

Exporting with a different Blender version can change serialization or
triangulation. No byte-identical re-export or raw-reference reconstruction is
promised. The existing `.usdz` is the verified publication snapshot.

## Check the downloaded collection

Python 3's standard library is sufficient:

```sh
python3 tools/check_catalog.py
```

This checks catalog counts, asset SHA-256 checksums, file sizes and USDZ archive
integrity. It does not update checksums for your edits automatically.
[Verification results](verification.json) also record the published assets'
geometry/UV/packed-image preservation, OpenUSD validation and native RealityKit
loading/centering. These establish asset integrity, not historical accuracy,
engineering tolerances or manufacturing suitability.
