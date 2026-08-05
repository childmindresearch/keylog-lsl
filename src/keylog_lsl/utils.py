"""Utilities for building keyboard event markers."""

import json
import time

from pylsl import StreamInfo


def get_key_string(key: object) -> str:
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


def make_marker(event: str, key: object) -> str:
    """Build a JSON marker payload.

    Args:
        event: The event type, either ``"press"`` or ``"release"``.
        key: The key object provided by ``pynput``.

    Returns:
        JSON string with ``event``, ``key``, and ``time_unix`` fields.
    """
    return json.dumps(
        {"event": event, "key": get_key_string(key), "time_unix": time.time()},
        ensure_ascii=False,
    )


def build_stream_info() -> StreamInfo:
    """Build and annotate the keyboard marker stream metadata.

    Returns:
        Configured ``pylsl.StreamInfo`` for the ``KeyboardEvents`` stream.
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

    return info
