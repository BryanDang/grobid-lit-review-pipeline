# Changes made during the cleanup

This repository is a clean copy of the project folder. Code that was moved aside is not included. All paths below are inside `projects/lit-review-pipeline/`.

## Moves
| From | To | Reason |
|---|---|---|
| `build_spine.py` | `scripts/build_spine.py` | Loose script at the project root. |
| `build_expand.py` | `scripts/build_expand.py` | Same. |
| `run_dryrun.py` | `scripts/run_dryrun.py` | Same. |
| `BUILD-BRIEF.md` | `docs/BUILD-BRIEF.md` | Loose report file at the project root. |

## Path edits needed by the moves (no other code changed)
- `scripts/*.py`: `HERE = Path(__file__).resolve().parent.parent` is set. That way `data/` and `corpus/` still resolve to the project root.
- `tests/test_spine.py` and `tests/test_expand.py`: the `sys.path.insert` line now points at `scripts/`.
- `scripts/run_dryrun.py`: the three `tei=` paths now point at `data/`. The old paths were `dryrun_pdfs/...` (two removed copies) and `../Research Extractor/Survey on Mech Interp.grobid.tei.xml`. That last file is not in this repository. `data/survey.grobid.tei.xml` is the copy the spine builder already uses. Unverified: whether it equals the missing original.

## Deletions (byte-for-byte identical files, as the root rules of the projects folder require)
| Deleted | Identical to | SHA-256 |
|---|---|---|
| `dryrun_pdfs/arXiv_2211.00593.grobid.tei.xml` | `data/IOI_2211.00593.grobid.tei.xml` | `2ebe3e44dd58257ae6d94dbaa158a09b95d0ee96fbc2f9bdc9d4bd55606da8ae` |
| `dryrun_pdfs/arXiv_2202.05262.grobid.tei.xml` | `data/ROME_2202.05262.grobid.tei.xml` | `bab4855882115b8213f1c6ed316c98914f85379d73c0f98e57862e5681e07008` |

The copy in `data/` stays: `scripts/build_spine.py` and `scripts/build_expand.py` name it. Open. See `docs/TECH-SPEC.md`, section "Open questions", item 1.

## Edits to notes
- 2026-11-02: removed a root notes file. The folder map moved into `README.md`.
- `docs/MODELS.md`: added the Download source table.
- `README.md`: updated the pointers to moved files.
- `docs/BUILD-BRIEF.md`: added a Contents section, because the file is over 100 lines.
- `tests/acceptance.md`: updated the `run_dryrun.py` pointer.

## Not touched
- `corpus/` was a separate repository in the original. Its `MANIFEST.json` paths are now relative. See `docs/TECH-SPEC.md`, section "TBD", item 7.
- No file is old or unused, and no version-suffixed names (v2, old, final) exist. Nothing was set aside.
