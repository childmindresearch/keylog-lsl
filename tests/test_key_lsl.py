"""Tests for the LSL keyboard event publisher."""

import json
import sys
from collections.abc import Callable
from importlib.metadata import entry_points
from types import ModuleType, SimpleNamespace
from typing import Self

import pytest

from keylog_lsl import key_lsl, utils


class _FakeNode:
    """Simple XML-like node for StreamInfo metadata tests."""

    def __init__(self) -> None:
        self.child_values: list[tuple[str, str]] = []
        self.child_nodes: dict[str, list["_FakeNode"]] = {}

    def append_child_value(self, key: str, value: str) -> None:
        """Store one key/value metadata pair."""
        self.child_values.append((key, value))

    def append_child(self, name: str) -> "_FakeNode":
        """Create and store one named child node."""
        child = _FakeNode()
        self.child_nodes.setdefault(name, []).append(child)
        return child


class _FakeStreamInfo:
    """Minimal StreamInfo stub exposing only ``desc``."""

    def __init__(self) -> None:
        self._desc = _FakeNode()

    def desc(self) -> _FakeNode:
        """Return mutable metadata root node."""
        return self._desc


def _patch_stream_info_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[_FakeStreamInfo, list[dict[str, object]]]:
    """Replace ``utils.StreamInfo`` with a controllable factory."""
    fake_info = _FakeStreamInfo()
    stream_info_calls: list[dict[str, object]] = []

    def stream_info_factory(**kwargs: object) -> _FakeStreamInfo:
        """Record constructor arguments and return a controlled stream."""
        stream_info_calls.append(kwargs)
        return fake_info

    monkeypatch.setattr(utils, "StreamInfo", stream_info_factory)
    return fake_info, stream_info_calls


class _FakeOutlet:
    """Record samples sent to an LSL outlet."""

    def __init__(self) -> None:
        self.samples: list[tuple[list[str], float]] = []

    def push_sample(self, sample: list[str], timestamp: float) -> None:
        """Store one sample and its LSL timestamp."""
        self.samples.append((sample, timestamp))


def _build_fake_keyboard(
    letter_key: object,
    escape_key: object,
    press_results: list[bool | None],
) -> SimpleNamespace:
    """Build a keyboard namespace whose listener replays deterministic events."""

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

    return SimpleNamespace(
        Key=SimpleNamespace(esc=escape_key),
        Listener=FakeListener,
    )


def test_keylog_script_calls_main() -> None:
    """Expose the publisher through the installed ``keylog-lsl`` command."""
    scripts = entry_points(group="console_scripts", name="keylog-lsl")
    script = next(iter(scripts))

    assert len(scripts) == 1
    assert script.value == "keylog_lsl.key_lsl:main"


def test_get_key_string() -> None:
    """Normalize character, named, and fallback key objects."""
    character_key = SimpleNamespace(char="a")
    named_key = SimpleNamespace(char=None, name="space")
    character_result = utils.get_key_string(character_key)
    named_result = utils.get_key_string(named_key)
    fallback_result = utils.get_key_string(42)

    assert character_result == "a"
    assert named_result == "space"
    assert fallback_result == "42"


def test_make_marker(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serialize an event, normalized key, and wall-clock timestamp."""
    monkeypatch.setattr(utils.time, "time", lambda: 123.5)

    marker = json.loads(utils.make_marker("press", SimpleNamespace(char="x")))

    assert marker == {"event": "press", "key": "x", "time_unix": 123.5}


def test_build_stream_info(monkeypatch: pytest.MonkeyPatch) -> None:
    """Build stream metadata with the expected channel and payload fields."""
    fake_info, stream_info_calls = _patch_stream_info_factory(monkeypatch)

    info = utils.build_stream_info()
    desc = fake_info.desc()
    channels = desc.child_nodes["channels"][0]
    channel = channels.child_nodes["channel"][0]
    payload = desc.child_nodes["payload"][0]

    assert info is fake_info
    assert stream_info_calls == [
        {
            "name": "KeyboardEvents",
            "type": "Markers",
            "channel_count": 1,
            "nominal_srate": 0,
            "channel_format": "string",
            "source_id": "python_keyboard_stream_01",
        }
    ]
    assert ("manufacturer", "pynput") in desc.child_values
    assert channel.child_values == [("label", "KeyboardEvent"), ("type", "Marker")]
    assert payload.child_values == [
        ("encoding", "json"),
        ("fields", "event,key,time_unix"),
        ("event_values", "press,release"),
        (
            "time_unix",
            "Wall-clock Unix epoch time in UTC seconds at the event, for "
            "post-hoc alignment with non-LSL data sources.",
        ),
    ]


def test_main_publishes_press_and_release(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Create the stream and publish a short, readable key sequence."""
    letter_key = SimpleNamespace(char="a")
    escape_key = SimpleNamespace(char=None, name="esc")
    press_results: list[bool | None] = []

    fake_keyboard = _build_fake_keyboard(letter_key, escape_key, press_results)
    pynput = ModuleType("pynput")
    pynput.keyboard = fake_keyboard  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pynput", pynput)

    stream_info = object()
    build_stream_info_calls: list[None] = []
    outlet_factory_calls: list[object] = []
    outlet = _FakeOutlet()

    def build_stream_info() -> object:
        """Record the factory call and return a controlled stream."""
        build_stream_info_calls.append(None)
        return stream_info

    def outlet_factory(info: object) -> _FakeOutlet:
        """Record the stream metadata and return a controlled outlet."""
        outlet_factory_calls.append(info)
        return outlet

    monkeypatch.setattr(utils, "build_stream_info", build_stream_info)
    monkeypatch.setattr(key_lsl, "StreamOutlet", outlet_factory)
    monkeypatch.setattr(utils, "local_clock", iter([1.0, 2.0, 3.0]).__next__)
    monkeypatch.setattr(utils.time, "time", lambda: 100.0)

    key_lsl.main()

    assert press_results == [None, False]
    assert build_stream_info_calls == [None]
    assert outlet_factory_calls == [stream_info]
    assert [
        (json.loads(sample[0]), timestamp) for sample, timestamp in outlet.samples
    ] == [
        ({"event": "press", "key": "a", "time_unix": 100.0}, 1.0),
        ({"event": "release", "key": "a", "time_unix": 100.0}, 2.0),
        ({"event": "press", "key": "esc", "time_unix": 100.0}, 3.0),
    ]

    output = capsys.readouterr().out
    assert "Broadcasting on LSL stream: 'KeyboardEvents'" in output
    assert "Stopping stream..." in output
