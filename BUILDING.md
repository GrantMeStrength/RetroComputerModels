# Editing, rebuilding and exporting

## Edit without rebuilding

Open any catalog `.blend` in Blender. All required image textures are packed.
Keep the supplied `Textures/` or `textures/` directory alongside the scene if you
want to edit an image externally. Do not stretch a photographic texture to a new
aspect ratio: its UV mapping is fitted to the supplied image.

Scenes contain named meshes and materials, not protected/frozen geometry.
Some are joined meshes rather than separate objects for every physical component.
Preview cameras, lights and grounds may remain in the scene for convenience.

## Reconstruct geometry from the distributed inputs

Tested with **Blender 5.2.1 LTS**. The builders use Blender's bundled Python,
`bmesh`, `mathutils` and, for some models, NumPy. No downloaded reference STL,
photo folder, application source tree or workstation-specific path is required.
Prepared textures, atlas/layout data and necessary authored dimensional inputs
are included. Python 3 is required for the launcher.

From this repository's root, with `blender` on PATH:

```sh
python3 tools/rebuild.py commodore64
python3 tools/rebuild.py appleIIe
python3 tools/rebuild.py timexSinclair1500
```

If needed, append `--blender "/path/to/Blender executable"`. On macOS a common
installation is `/Applications/Blender.app/Contents/MacOS/Blender`.
Model identifiers are the stems of `.blend` files in `catalog.json`:

```text
commodore64 vic20 researchMachines380Z bbcMicro amstradCPC464 zx81
jupiterAce electron-review appleIIe spectrum-plus2 zxSpectrum timexSinclair1500
```

Outputs go to **`build/ModelSources/<family>/`**, leaving the catalog assets
unchanged. Run one build at a time because builders in a family share the output
directory. The default skips preview rendering; add `--render` to run the original
builder's inspection views. The Jupiter Ace builder exports only its model and
does not define a render rig; its existing catalog preview remains available.
Blender is started headlessly with two threads; no running GUI scene is touched.
Generated inspection reports are local build products, not historical certification.

The source builders in `ModelSources/` can also be studied directly, but running
them there overwrites their local outputs. Use the launcher to preserve the
distributed versions. The Apple IIe builder includes the final centered-keyboard
operation; it does not need an earlier scene backup.

### Reproducibility boundary

These commands reconstruct geometry and export using **the supplied prepared
textures**. They do not regenerate source photographs, recover reference mesh
files, reproduce photographic measurement studies, or rerun the full artwork
preparation pipeline. Original inputs not required for construction have been
intentionally omitted. The exact distributed texture pixels are the reproducible
artwork inputs; edit them in an image editor if desired.

Re-running Blender can change serialization order, triangulation or package bytes
between releases. A successful build is not a promise of byte-identical USDZ or
Blender output. The catalog checksums identify the published USDZ files. The
original model geometry/artwork was preserved during publication; metadata-only
Blender packaging did not rebuild the shapes.

## Export an edited Blender scene

Choose a **new** output path:

```sh
blender --background --factory-startup --python-exit-code 1 \
  --python tools/export_blend.py -- \
  ModelSources/AppleIIReferenceRebuild/appleIIe.blend build/exports/appleIIe.usdz
```

The helper selects model meshes and excludes named preview/review studio aids.
It exports materials and embedded textures, metres/Y-up, without cameras,
lights, world environments or custom properties. It refuses to overwrite an
existing output. If you add your own studio objects, retain the `Preview` or
`ReviewOnly` naming convention, or put them in a preview/studio collection.

## Validate USDZ

Check the distributed catalog counts, asset checksums and archive integrity using
only Python's standard library:

```sh
python3 tools/check_catalog.py
```

Checksums identify the publication snapshot; edits/rebuilds are intentionally not
substituted into the catalog automatically.

The validator requires the **OpenUSD Python package `usd-core`**, including
`UsdValidation`. Use an environment that already provides it, or with `uv`:

```sh
uv run --with usd-core python ModelSources/validate_model.py \
  ModelSources/WebPrototypes/commodore64.usdz \
  ModelSources/BritishModels/bbcMicro.usdz
```

Substitute any number of catalog or rebuilt USDZ paths. It checks closed,
consistently wound nondegenerate triangles, UV data, package alignment,
embedded dependencies, stage orientation and standard USD validation.
These checks establish asset integrity, not manufacturing suitability or
historical accuracy.
