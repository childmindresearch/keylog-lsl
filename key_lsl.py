# /// script
# dependencies = [
#     "pynput",
#     "pylsl",
# ]
# ///

"""Publish keyboard markers to LSL.

This script captures global key presses and releases and writes them to one
LSL marker stream named ``KeyboardEvents``.

Each marker is JSON with:
- ``event``: ``press`` or ``release``
- ``key``: normalized key name
- ``time_unix``: wall-clock Unix timestamp

LSL sample timestamps are set with ``pylsl.local_clock()`` at callback time.
This gives an ``(lsl_time, time_unix)`` pair for each event, which is useful
for post-hoc alignment with non-LSL logs such as browser UI timestamps.

Run with:
        uv run key_lsl.py

Press ``ESC`` to stop.
"""

import json
import time
from typing import Any, Optional

from pylsl import StreamInfo, StreamOutlet, local_clock
from pynput import keyboard


def _get_key_string(key: Any) -> str:
    """Return a normalized key name.

    Args:
        key: The key object provided by ``pynput``. This is a
            ``keyboard.KeyCode`` for character keys or a ``keyboard.Key`` for
            special keys (for example, ``SHIFT``).

    Returns:
        Character keys as-is and named keys without the ``Key.`` prefix.
    """
    char = getattr(key, "char", None)
    if char is not None:
        return str(char)
    name = getattr(key, "name", None)
    if name is not None:
        return str(name)
    return str(key)


def _make_marker(event: str, key: Any) -> str:
    """Build a JSON marker payload.

    Args:
        event: The event type, either ``"press"`` or ``"release"``.
        key: The key object provided by ``pynput``.

    Returns:
        JSON string with ``event``, ``key``, and ``time_unix`` fields.
    """
    return json.dumps(
        {"event": event, "key": _get_key_string(key), "time_unix": time.time()},
        ensure_ascii=False,
    )


def main() -> None:
    """Create the marker outlet and stream events until ``ESC``.

    The stream uses one irregular-rate string channel with type ``Markers``.
    Stream ``desc`` metadata documents the channel and JSON payload fields.
    """
    info = StreamInfo(
        name="KeyboardEvents",
        type="Markers",
        channel_count=1,
        nominal_srate=0,  # IRREGULAR_RATE
        channel_format="string",
        source_id="python_keyboard_stream_01",
    )

    desc = info.desc()
    desc.append_child_value("manufacturer", "pynput")
    channel = desc.append_child("channels").append_child("channel")
    channel.append_child_value("label", "KeyboardEvent")
    channel.append_child_value("type", "Marker")
    payload = desc.append_child("payload")
    payload.append_child_value("encoding", "json")
    payload.append_child_value("fields", "event,key,time_unix")
    payload.append_child_value("event_values", "press,release")
    payload.append_child_value(
        "time_unix",
        "Wall-clock Unix epoch seconds at the event, for post-hoc alignment "
        "with non-LSL data sources.",
    )

    outlet = StreamOutlet(info)

    print("--- LSL Keyboard Event Streamer ---")
    print("Broadcasting on LSL stream: 'KeyboardEvents'")
    print('Marker payload: JSON with fields "event", "key", "time_unix"')
    print("Listening for keystrokes... (Press ESC to stop)")

    def on_press(key: Any) -> Optional[bool]:
        """Push a press marker and stop the listener on Escape.

        Args:
            key: The key that was pressed, as provided by ``pynput``.

        Returns:
            ``False`` to stop the keyboard listener when Escape is pressed;
            otherwise ``None`` to keep listening.
        """
        lsl_time = local_clock()
        marker = _make_marker("press", key)
        outlet.push_sample([marker], lsl_time)
        print(f"Pushed to LSL: {marker}")

        if key == keyboard.Key.esc:
            print("Stopping stream...")
            return False
        return None

    def on_release(key: Any) -> None:
        """Push a release marker for the given key.

        Args:
            key: The key that was released, as provided by ``pynput``.
        """
        lsl_time = local_clock()
        marker = _make_marker("release", key)
        outlet.push_sample([marker], lsl_time)
        print(f"Pushed to LSL: {marker}")

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()


if __name__ == "__main__":
    main()
