# keylog-lsl

Python tool for keyboard event logging over LSL and basic text reconstruction.

This repository has two scripts:

- `key_lsl.py`: records global keyboard events and publishes them to an LSL
	marker stream named `KeyboardEvents`.
- `example_key_analysis.py`: example analysis code for reconstructing typed
	text from recorded markers.

These script is intended as a module but it also works as a standalone CLI.

## Requirements

- Python 3.10+
- `uv`

## Quick start

Run the keyboard stream publisher:

```bash
uv run key_lsl.py
```

This opens an LSL stream named `KeyboardEvents` with JSON markers:

```json
{"event":"press","key":"a","time_unix":1760000000.1234}
```

Press `ESC` to stop.

## Analyze a marker CSV

If you already have a marker CSV (columns: `timestamp`, `marker`):

```bash
uv run example_key_analysis.py path/to/keyboard_markers.csv
```

## Analyze an XDF file

If your recording is in XDF:

```bash
uv run example_key_analysis.py path/to/session.xdf
```

Optional: choose where exported CSVs are written:

```bash
uv run example_key_analysis.py path/to/session.xdf --xdf-output-dir path/to/out
```

## Useful analysis flags

```bash
# show one annotated line per event
uv run example_key_analysis.py path/to/session.xdf --show-events

# collapse character auto-repeat (held-key repeats)
uv run example_key_analysis.py path/to/session.xdf --collapse-repeats
```

## What the analysis prints

Typical output structure:

```text
--- Reconstructed input ---
first line
second line

--- Stats ---
events: ...
	presses: ...
	releases: ...
chars inserted: ...
backspaces applied: ...
auto-repeat presses: ...
session duration: ... s
```

Notes:

- Unmodeled keys are keys with no defined effect on the reconstructed text
  (for example arrow keys, delete, home/end, function keys). They're skipped
  rather than guessed at, so if they show up in the stats, the reconstructed
  text may not exactly match what was actually typed.
