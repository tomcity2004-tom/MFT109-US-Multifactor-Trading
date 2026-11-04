# Phase 10B — Final Results Export and Documentation

## Scope and preservation

Package existing Phase 0–10A evidence for later academic report/presentation use.
No strategy, metric, sensitivity or statistical-method change. No final course
report, PPT or submission archive is created. Phase 10A checkpoint is
`fcb2633b5dd5271774a281d271f87474cb3febe2`.

New export utility: `mft109/analysis/final_exports.py`.
Default output: `outputs/final_report/v1/`, deliberately eligible for Git tracking.
No broad ignore change or raw-cache inclusion is needed. Original ignored
`outputs/final_analysis/`, historical outputs and dashboard artifacts are untouched.

The package has ten CSVs, thirteen figures, copied Phase 10A metadata and
interpretation, and a manifest: 26 files. See FINAL_EXPORT_INDEX.md for paths,
units, copies versus presentation exports and data-vintage rules. All six
sensitivity groups and 21 rows are retained, not reordered by performance.

## Inputs and reproducibility

Use current tracked `dashboard/data/`, locked configuration/specification,
fixed universe, reviewed provenance/validation documents and approved Phase 10A
outputs. The utility validates Phase 10A source/version/code/output hashes,
then copies tables/plots and renders new figures from saved data only. It does
not run the factor/backtest/sensitivity pipeline or recompute normality tests.

```bash
python -m pip install -r requirements-analysis.txt
# Only if approved ignored Phase 10A outputs are absent:
python -B -m mft109.analysis.data_analysis
python -B -m mft109.analysis.final_exports
```

The fixed checkpoint, exporter hash, source hashes, methodology hash, package
version and software versions identify the package. No changing generation
timestamp is inserted. Missing/corrupt input or an unrelated destination file
fails explicitly; sources are rechecked after export. Protected destinations
are rejected. The manifest inventories all files except itself, avoiding a
self-referential checksum. Copied Phase 10A metadata describes its original
folder; final-package paths are in the outer manifest.

## Documentation changes

README is condensed to current course context, strategy, results, installation,
run/test commands and links. New final methodology/results, limitations,
reproducibility, export-index and assignment-mapping documents consolidate the
validated research without deleting historical phase records. Older quality
reports are clearly historical; no new vendor audit or updated missing-data
statistics are fabricated.

## Validation

Tests cover exact metrics, yearly coverage, methodology/formula tables, scenario
identity/order, Phase 10A byte preservation, manifest paths/hashes, static figures,
source immutability, failure handling, deterministic regeneration and final-doc
references. Prior Phase 10A/core/dashboard tests remain unchanged.

```bash
MFT109_REQUIRE_APPROVED_CACHE=1 python -B -m unittest discover -s tests -v
python -B -m unittest discover -s tests -p test_data_analysis.py -v
python -B -m unittest discover -s tests -p test_final_exports.py -v
python -B -m pip check
git diff --check
```

Full quantitative validation requires the approved local cache. Dashboard and
inspection of the tracked report package do not. Statistical/package regeneration
requires analysis dependencies and the explicit input steps above.

Final validation:

| Check | Result |
| --- | --- |
| Phase 10A targeted tests | 24 passed; 0 failures/errors; 0 skipped |
| New Phase 10B tests | 18 passed; 0 failures/errors; 0 skipped |
| Complete approved-cache suite | 446 passed; 0 failures/errors; 0 skipped |
| Prior tests | All 428 passed, including 54 dashboard/bilingual tests |
| Repeat final export | All 26 files byte-identical |
| Phase 10A copies | CSVs, four PNGs, metadata and interpretation byte-identical |
| Clean repository-only dashboard | All five pages in both languages passed, without SciPy or ignored research files |
| Headless app shell / health | HTTP 200 / HTTP 200 |
| Dependency and whitespace checks | PASS |
| Protected existing files | 1,176 unchanged; README alone intentionally updated |

Representative new NAV, drawdown, annual and factor-weight figures were visually
inspected; all thirteen PNGs passed dimensions/checksum tests. No graphical
browser or live Community Cloud redeployment was performed. Existing Streamlit
bare-mode and Phase 1 invalid-date/mocked-data diagnostics remain expected;
there were no test/application failures.

The 26-file package is approximately 3.05 MB (2.91 MiB), with no raw Yahoo caches,
credentials or runtime files. All source/result hashes match; no obsolete
baseline is restored. Work remains uncommitted for review. No merge, push, pull
request, final report or PPT is part of this phase.

**PHASE 10B READY FOR REVIEW: YES**
