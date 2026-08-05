"""Tests for the LSL keyboard event publisher."""

import json
import sys
from collections.abc import Callable
from importlib.metadata import entry_points
from types import ModuleType, SimpleNamespace
from typing import Self
from unittest.mock import MagicMock

import pytest

from keylog_lsl import key_lsl


def test_keylog_script_calls_main() -> None:
    """Expose the publisher through the installed ``keylog-lsl`` command."""
    scripts = entry_points(group="console_scripts", name="keylog-lsl")

    assert len(scripts) == 1
    assert next(iter(scripts)).value == "keylog_lsl.key_lsl:main"


def test_get_key_string() -> None:
    """Normalize character, named, and fallback key objects."""
    character_key = SimpleNamespace(char="a")
    named_key = SimpleNamespace(char=None, name="space")

    assert key_lsl._get_key_string(character_key) == "a"
    assert key_lsl._get_key_string(named_key) == "space"
    assert key_lsl._get_key_string(42) == "42"


def test_make_marker(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serialize an event, normalized key, and wall-clock timestamp."""
    monkeypatch.setattr(key_lsl.time, "time", lambda: 123.5)

    marker = json.loads(key_lsl._make_marker("press", SimpleNamespace(char="x")))

    assert marker == {"event": "press", "key": "x", "time_unix": 123.5}


def test_main_publishes_press_and_release(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Create the stream and publish a short, readable key sequence."""
    letter_key = SimpleNamespace(char="a")
    escape_key = SimpleNamespace(char=None, name="esc")
    press_results: list[bool | None] = []

    class FakeListener:
        """Run keyboard callbacks synchronously without reading real input."""

        def __init__(
            self,
            *,
            on_press: Callable[[object], bool | None],
            on_release: Callable[[object], None],
        ) -> None:
            self.on_press = on_press
            self.on_release = on_release

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def join(self) -> None:
            """Replay one character press/release followed by Escape."""
            press_results.append(self.on_press(letter_key))
            self.on_release(letter_key)
            press_results.append(self.on_press(escape_key))

    keyboard = SimpleNamespace(
        Key=SimpleNamespace(esc=escape_key),
        Listener=FakeListener,
    )
    pynput = ModuleType("pynput")
    pynput.keyboard = keyboard  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pynput", pynput)

    stream_info = MagicMock()
    stream_info_factory = MagicMock(return_value=stream_info)
    outlet = MagicMock()
    outlet_factory = MagicMock(return_value=outlet)
    monkeypatch.setattr(key_lsl, "StreamInfo", stream_info_factory)
    monkeypatch.setattr(key_lsl, "StreamOutlet", outlet_factory)
    monkeypatch.setattr(key_lsl, "local_clock", MagicMock(side_effect=[1.0, 2.0, 3.0]))
    monkeypatch.setattr(key_lsl.time, "time", lambda: 100.0)

    key_lsl.main()

    assert press_results == [None, False]
    stream_info_factory.assert_called_once_with(
        name="KeyboardEvents",
        type="Markers",
        channel_count=1,
        nominal_srate=0,
        channel_format="string",
        source_id="python_keyboard_stream_01",
    )
    outlet_factory.assert_called_once_with(stream_info)
    assert [
        (json.loads(push.args[0][0]), push.args[1])
        for push in outlet.push_sample.call_args_list
    ] == [
        ({"event": "press", "key": "a", "time_unix": 100.0}, 1.0),
        ({"event": "release", "key": "a", "time_unix": 100.0}, 2.0),
        ({"event": "press", "key": "esc", "time_unix": 100.0}, 3.0),
    ]

    output = capsys.readouterr().out
    assert "Broadcasting on LSL stream: 'KeyboardEvents'" in output
    assert "Stopping stream..." in output
