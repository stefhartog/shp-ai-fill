# Source provenance

AI Fill was split out of [stefhartog/shp-portrait-tools](https://github.com/stefhartog/shp-portrait-tools)
at `a7d692d`. This is a new repository; that project's history is not carried over.

| Copied from shp-portrait-tools | Here |
|---|---|
| `src/shp_photocraft_tools/modules/crop/` | `src/shp_ai_fill/` |
| `src/shp_photocraft_tools/shared/` (the helpers AI Fill imports) | `src/shp_ai_fill/shared/` |
| `comfyui/custom_nodes/seam-color-correct/` | unchanged |
| AI Fill tests, `MODELS.md` ComfyUI section, `docs/source/crop-*.md` | `tests/`, `MODELS.md`, `docs/source/` |

The shared helpers are copies. Fixes to them in shp-portrait-tools are not applied here automatically.
AI Fill originally came from [stefhartog/shpcrop](https://github.com/stefhartog/shpcrop)
at `7e07a3fbea337af4f590ff3e258156cce4383901`; `docs/source/` keeps those historical notes.
