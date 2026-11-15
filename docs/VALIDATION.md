# Validation

First public-release validation was performed on **2026-11-15**, on macOS, using factory-startup background Blender processes. The tests were run against the release source, separately for each version.

| Suite | What it checks | Blender 4.3.2 | Blender 5.1.0 |
| --- | --- | --- | --- |
| `verify_addon.py` | Tracking, independent cameras, focus restoration, save/reopen | 37 assertions passed | 37 assertions passed |
| `verify_motion.py` | All 14 presets, progress, loops, edits, restoration, native reload | 393 assertions passed | 393 assertions passed |
| `verify_shots.py` | Endpoint projection, lens data, segments, preview state, native reload | 235 assertions passed | 235 assertions passed |
| `verify_picker.py` | Picker assignment, cancel/retry logic, selection preservation | 33 assertions passed | 33 assertions passed |
| Total | Four suites | **698 assertions** | **698 assertions** |

Reproduce with `python3 scripts/run_tests.py --blender /path/to/blender`. These are integration checks and assertions, not 698 independent user scenarios. Picker event logic uses controlled stubs for some UI operations; the results do not imply every mouse interaction/layout has been manually tested.

The add-on declares Blender 4.2 as its minimum. Other releases and operating systems have not been confirmed by this validation. The downloadable example is created using Blender 4.3.2; it uses native paths/constraints and no external assets.

GitHub Actions performs Python syntax checks, builds the installable archive and verifies its contents. Blender integration suites are currently run locally. The workflow badge describes packaging status.
