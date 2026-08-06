"""Utilities for building keyboard event markers."""

import json
import time

from pylsl import StreamInfo, StreamOutlet, local_clock


def get_key_string(key: object) -> str:
    """Return a normalized string representation of a pynput key event.

    In ``pynput``, keystrokes generate different object types based on the key pressed.
        Standard character keys generate ``keyboard.KeyCode`` objects which utilize a 
        ``char`` attribute. Special or modifier keys generate ``keyboard.Key`` Enum 
        objects which utilize a ``name`` attribute. This function normalizes both into a
        clean string.

    Args:
        key: The key object provided by the ``pynput`` listener. This is typically a
            ``keyboard.KeyCode`` for typable keys (e.g., 'a', '5') or a
            ``keyboard.Key`` for special keys (e.g., ``Key.shift``, ``Key.space``).

    Returns:
        str: A clean string representation of the keystroke.
            - For character keys, returns the literal character via the ``char``
            attribute (e.g., returning "a" instead of the default "'a'").
            - For special keys, returns the key name via the ``name`` attribute
            (e.g., returning "shift" instead of the default "Key.shift").
            - If a key object exposes both attributes, ``char`` takes precedence to
            preserve the typed character exactly.
            - If neither attribute exists (e.g., unmapped hardware or media keys),
            it falls back to the default ``str(key)`` representation.
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


def push_marker(outlet: StreamOutlet, event: str, key: object) -> None:
    """Publish one keyboard event marker to the active LSL outlet.

    Args:
        outlet: The LSL outlet receiving event markers.
        event: The event type, either ``"press"`` or ``"release"``.
        key: The key object provided by ``pynput``.
    """
    lsl_time = local_clock()
    marker = make_marker(event, key)
    outlet.push_sample([marker], lsl_time)
    print(f"Pushed to LSL: {marker}")  # will remove in the future
