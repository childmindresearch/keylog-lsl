# /// script
# dependencies = [
#     "pyxdf",
# ]
# ///

"""Example analysis script for KeyboardEvents marker data.

This file is an example analysis script for data produced by ``key_lsl.py``.

Accepted input:
- Marker CSV with columns ``timestamp`` and ``marker``
- XDF file (the script exports streams to CSV, then analyzes the marker stream)

CLI usage:
        uv run example_key_analysis.py path/to/markers.csv
        uv run example_key_analysis.py path/to/session.xdf
        uv run example_key_analysis.py path/to/session.xdf --show-events
        uv run example_key_analysis.py path/to/session.xdf --collapse-repeats

Output includes:
- Reconstructed text (Enter is treated as a newline, not a submit action)
- Reconstruction stats (presses, releases, backspaces, repeats, duration)
"""

import argparse
import csv
import json
import os
from typing import Any, Dict, List, Optional, Tuple


def _safe_name(value: str) -> str:
    """Return a file-safe stream name."""
    return "".join(char if char.isalnum() else "_" for char in value)


def _is_sequence(value: Any) -> bool:
    """Return True when value looks like a non-string sequence."""
    if isinstance(value, (str, bytes)):
        return False
    return isinstance(value, (list, tuple))


def _flatten_marker(sample: Any) -> str:
    """Return marker text from one marker sample."""
    if _is_sequence(sample):
        if not sample:
            return ""
        return str(sample[0])
    return str(sample)


def _normalize_legacy_key(raw_key: str) -> str:
    """Normalize old marker key strings into analysis key names."""
    key = raw_key.strip()
    if key.startswith("Key."):
        key = key[4:]
    return key


def _parse_marker_row(marker_text: str) -> Dict[str, Any]:
    """Parse marker text from either JSON or legacy formats.

    Supported non-JSON formats:
    - press_x / release_x
    - Key.space / Key.enter / a
    """
    text = marker_text.strip()
    if not text:
        return {"event": "press", "key": "", "time_unix": None}

    if text.startswith("{"):
        payload = json.loads(text)
        return {
            "event": payload.get("event", "press"),
            "key": str(payload.get("key", "")),
            "time_unix": payload.get("time_unix"),
        }

    if text.startswith("press_"):
        return {
            "event": "press",
            "key": _normalize_legacy_key(text[len("press_") :]),
            "time_unix": None,
        }

    if text.startswith("release_"):
        return {
            "event": "release",
            "key": _normalize_legacy_key(text[len("release_") :]),
            "time_unix": None,
        }

    return {
        "event": "press",
        "key": _normalize_legacy_key(text),
        "time_unix": None,
    }


def export_xdf_to_csv(
    xdf_path: str,
    output_dir: Optional[str] = None,
) -> Tuple[List[str], Optional[str]]:
    """Export XDF streams to CSV files.

    Args:
        xdf_path: Path to the source XDF file.
        output_dir: Directory for CSV outputs. Defaults to XDF file directory.

    Returns:
        Tuple of (all exported CSV paths, detected KeyboardEvents marker CSV).
    """
    import pyxdf

    if not os.path.exists(xdf_path):
        raise FileNotFoundError(f"File not found: {xdf_path}")

    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(xdf_path))
    os.makedirs(output_dir, exist_ok=True)

    print(f"Loading XDF: {xdf_path}")
    streams, _ = pyxdf.load_xdf(xdf_path)
    print(f"Found {len(streams)} stream(s). Exporting CSV files...")

    exported_csvs: List[str] = []
    keyboard_csv: Optional[str] = None

    for index, stream in enumerate(streams):
        info = stream.get("info", {})
        stream_name = info.get("name", [f"stream_{index}"])[0]
        stream_type = info.get("type", ["unknown"])[0]
        safe_name = _safe_name(str(stream_name))
        csv_name = f"{safe_name}_{stream_type}.csv"
        csv_path = os.path.join(output_dir, csv_name)

        timestamps = stream.get("time_stamps", [])
        time_series = stream.get("time_series", [])

        with open(csv_path, "w", newline="", encoding="utf-8") as file_obj:
            writer = csv.writer(file_obj)
            if str(stream_type).lower() == "markers":
                writer.writerow(["timestamp", "marker"])
                for timestamp, sample in zip(timestamps, time_series):
                    writer.writerow([timestamp, _flatten_marker(sample)])
            else:
                first = time_series[0] if time_series else []
                if _is_sequence(first):
                    width = len(first)
                elif time_series:
                    width = 1
                else:
                    width = 0
                header = ["timestamp"] + [f"ch_{i}" for i in range(width)]
                writer.writerow(header)
                for timestamp, sample in zip(timestamps, time_series):
                    if _is_sequence(sample):
                        row = list(sample)
                    else:
                        row = [sample]
                    writer.writerow([timestamp] + row)

        exported_csvs.append(csv_path)
        print(f"  -> {csv_path}")

        if (
            str(stream_type).lower() == "markers"
            and str(stream_name) == "KeyboardEvents"
        ):
            keyboard_csv = csv_path

    if keyboard_csv is None:
        for csv_path in exported_csvs:
            if csv_path.lower().endswith("_markers.csv"):
                keyboard_csv = csv_path
                break

    return exported_csvs, keyboard_csv

#: Keys that never produce text and only gate other keys.
MODIFIER_KEYS = {
    "shift", "shift_l", "shift_r",
    "ctrl", "ctrl_l", "ctrl_r",
    "alt", "alt_l", "alt_r", "alt_gr",
    "cmd", "cmd_l", "cmd_r",
    "caps_lock",
}

#: Modifiers that turn a character press into a (non-text) shortcut.
SHORTCUT_MODIFIERS = {"ctrl", "ctrl_l", "ctrl_r", "cmd", "cmd_l", "cmd_r"}

#: Named keys that insert literal text.
NAMED_TEXT_KEYS = {"space": " ", "tab": "\t", "enter": "\n"}

#: Named keys that are intentionally ignored (no effect on the buffer).
IGNORED_KEYS = {"esc"}

# If the same key is pressed again without a release, treat it as true
# auto-repeat only when the gap is short enough to match OS key-repeat cadence.
# Longer gaps are more likely a missed release in the recording.
AUTO_REPEAT_MAX_INTERVAL_S = 0.50


def load_events(csv_path: str) -> List[Dict[str, Any]]:
    """Load and sort events from a marker CSV file.

    Args:
        csv_path: Path to a CSV file with columns ``timestamp`` (LSL time,
            float seconds) and ``marker`` (JSON string with fields ``event``,
            ``key``, and ``time_unix``).

    Returns:
        Sorted event dicts with ``lsl_time``, ``event``, ``key``, and
        ``time_unix``.
    """
    events: List[Dict[str, Any]] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            payload = _parse_marker_row(row["marker"])
            events.append(
                {
                    "lsl_time": float(row["timestamp"]),
                    "event": payload["event"],
                    "key": payload["key"],
                    "time_unix": payload.get("time_unix"),
                }
            )
    events.sort(key=lambda e: e["lsl_time"])
    return events


def reconstruct(
    events: List[Dict[str, Any]],
    collapse_repeats: bool = False,
    show_events: bool = False,
) -> Tuple[str, Dict[str, Any]]:
    """Replay events and reconstruct typed text.

    Args:
        events: Ordered event dicts as returned by :func:`load_events`.
        collapse_repeats: If True, drop characters coming from OS auto-repeat
            instead of keeping them. Backspace auto-repeat is never
            collapsed, because a held Backspace really does keep deleting.
        show_events: If True, print one annotated line per event describing
            the action taken (useful for debugging the reconstruction).

    Returns:
        Tuple of ``(text, stats)``.

        ``text`` is the full reconstructed text. ``stats`` stores event and
        reconstruction counters.
    """
    buffer: List[str] = []
    held_since: Dict[str, float] = {}
    has_release_events = any(ev["event"] == "release" for ev in events)
    stats: Dict[str, Any] = {
        "events": len(events),
        "presses": 0,
        "releases": 0,
        "chars_inserted": 0,
        "backspaces_applied": 0,
        "auto_repeat_presses": 0,
        "repeats_collapsed": 0,
        "stale_held_resets": 0,
        "shortcuts_skipped": 0,
        "unmodeled": {},
    }

    def log(ev: Dict[str, Any], action: str) -> None:
        if show_events:
            print(
                f"{ev['lsl_time']:.4f}  {ev['event']:<7} {ev['key']!r:<12} -> {action}"
            )

    for ev in events:
        key = ev["key"]

        if ev["event"] == "release":
            stats["releases"] += 1
            held_since.pop(key, None)
            log(ev, "release")
            continue

        stats["presses"] += 1
        is_repeat = False
        if has_release_events:
            prev_press_time = held_since.get(key)
            if prev_press_time is not None:
                delta = ev["lsl_time"] - prev_press_time
                if delta <= AUTO_REPEAT_MAX_INTERVAL_S:
                    is_repeat = True
                    stats["auto_repeat_presses"] += 1
                else:
                    stats["stale_held_resets"] += 1
                    log(ev, f"stale held key reset (gap={delta:.3f}s)")
            held_since[key] = ev["lsl_time"]

        if key in MODIFIER_KEYS or key in IGNORED_KEYS:
            log(ev, "modifier/ignored")
            continue

        if key == "backspace":
            if buffer:
                removed = buffer.pop()
                stats["backspaces_applied"] += 1
                log(ev, f"backspace (removed {removed!r})")
            else:
                log(ev, "backspace (buffer empty)")
            continue

        # Resolve the text this key inserts, if any.
        char: Optional[str] = NAMED_TEXT_KEYS.get(key)
        if char is None and len(key) == 1 and key.isprintable():
            char = key

        if char is None:
            stats["unmodeled"][key] = stats["unmodeled"].get(key, 0) + 1
            log(ev, "unmodeled key (reconstruction may drift)")
            continue

        if has_release_events and set(held_since) & SHORTCUT_MODIFIERS:
            stats["shortcuts_skipped"] += 1
            log(ev, "shortcut (ctrl/cmd held), skipped")
            continue

        if is_repeat and collapse_repeats:
            stats["repeats_collapsed"] += 1
            log(ev, f"auto-repeat {char!r} collapsed")
            continue

        buffer.append(char)
        stats["chars_inserted"] += 1
        log(ev, f"insert {char!r}" + (" (auto-repeat)" if is_repeat else ""))

    if events:
        stats["session_duration_s"] = events[-1]["lsl_time"] - events[0]["lsl_time"]
    else:
        stats["session_duration_s"] = 0.0

    return "".join(buffer), stats


def main() -> None:
    """Parse CLI args, run reconstruction, and print a summary."""
    parser = argparse.ArgumentParser(
        description=(
            "Reconstruct typed text from KeyboardEvents markers in CSV or XDF."
        )
    )
    parser.add_argument(
        "input_path",
        help="Path to marker CSV or XDF file",
    )
    parser.add_argument(
        "--xdf-output-dir",
        default=None,
        help="Directory for CSVs exported from XDF (defaults to XDF folder)",
    )
    parser.add_argument(
        "--collapse-repeats",
        action="store_true",
        help="drop characters produced by OS key auto-repeat",
    )
    parser.add_argument(
        "--show-events",
        action="store_true",
        help="print an annotated line per event (debugging)",
    )
    args = parser.parse_args()

    input_path = args.input_path
    input_ext = os.path.splitext(input_path)[1].lower()

    if input_ext == ".xdf":
        exported_csvs, keyboard_csv = export_xdf_to_csv(
            input_path,
            output_dir=args.xdf_output_dir,
        )
        if not keyboard_csv:
            raise ValueError(
                "No marker stream found in XDF export. "
                "Expected a KeyboardEvents Markers stream."
            )
        print(f"Using marker CSV for analysis: {keyboard_csv}")
        print(f"Exported {len(exported_csvs)} CSV file(s).")
        marker_csv_path = keyboard_csv
    elif input_ext == ".csv":
        marker_csv_path = input_path
    else:
        raise ValueError("Input must be .csv or .xdf")

    events = load_events(marker_csv_path)
    text, stats = reconstruct(
        events,
        collapse_repeats=args.collapse_repeats,
        show_events=args.show_events,
    )

    print("--- Reconstructed input ---")
    print(text if text else "(no text)")

    print("\n--- Stats ---")
    print(f"events:              {stats['events']}")
    print(f"  presses:           {stats['presses']}")
    print(f"  releases:          {stats['releases']}")
    print(f"chars inserted:      {stats['chars_inserted']}")
    print(f"backspaces applied:  {stats['backspaces_applied']}")
    print(f"auto-repeat presses: {stats['auto_repeat_presses']}")
    if stats["repeats_collapsed"]:
        print(f"repeats collapsed:   {stats['repeats_collapsed']}")
    if stats["stale_held_resets"]:
        print(f"stale held resets:   {stats['stale_held_resets']}")
    if stats["shortcuts_skipped"]:
        print(f"shortcuts skipped:   {stats['shortcuts_skipped']}")
    print(f"session duration:    {stats['session_duration_s']:.2f} s")
    if stats["unmodeled"]:
        print("unmodeled keys (reconstruction may be unreliable):")
        for key, count in sorted(stats["unmodeled"].items()):
            print(f"  {key}: {count}")


if __name__ == "__main__":
    main()
