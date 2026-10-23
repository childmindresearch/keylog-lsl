"""Tests for the LSL keyboard event publisher."""

import json
import sys
from collections.abc import Callable
from importlib.metadata import entry_points
from types import ModuleType, SimpleNamespace

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


class _FakeListener:
    """Track a single-use listener without reading real keyboard input."""

    def __init__(
        self,
        *,
        on_press: Callable[[object], None],
        on_release: Callable[[object], None],
    ) -> None:
        self.on_press = on_press
        self.on_release = on_release
        self.started = False
        self.ready = False
        self.running = False
        self.stop_calls = 0
        self.join_calls = 0
        self.error: Exception | None = None

    def start(self) -> None:
        """Start this listener exactly once, as required by pynput."""
        assert not self.started
        self.started = True
        self.running = True

    def stop(self) -> None:
        """Stop receiving events."""
        self.stop_calls += 1
        self.running = False

    def wait(self) -> None:
        """Finish keyboard-layout initialization before the GUI is created."""
        assert self.started
        self.ready = True

    def join(self) -> None:
        """Wait for shutdown and surface any callback failure."""
        self.join_calls += 1
        assert not self.running
        if self.error is not None:
            raise self.error

    def is_alive(self) -> bool:
        """Report whether the listener is still running."""
        return self.running


class _FakeLabel:
    """Record the window's descriptive label without Tk."""

    def __init__(self, master: "_FakeWindow", *, text: str) -> None:
        self.text = text
        master.label = self

    def pack(self, **kwargs: object) -> None:
        """Accept layout options without creating a real widget."""


class _FakeButton:
    """Expose the control button's label and command without Tk."""

    def __init__(
        self,
        master: "_FakeWindow",
        *,
        text: str,
        command: Callable[[], None],
        width: int,
    ) -> None:
        self.text = text
        self.state = "normal"
        self.command = command
        master.button = self

    def pack(self, **kwargs: int) -> None:
        """Accept layout options without creating a real widget."""

    def configure(self, *, text: str, state: str = "normal") -> None:
        """Update the visible button label."""
        self.text = text
        self.state = state


class _FakeWindow:
    """Run scripted UI actions without requiring a desktop display."""

    def __init__(self) -> None:
        self.button: _FakeButton | None = None
        self.label: _FakeLabel | None = None
        self.minimum_size: tuple[int, int] | None = None
        self.close_callback: Callable[[], None] | None = None
        self.on_mainloop: Callable[[], None] = self.close
        self.scheduled: list[Callable[[], None]] = []
        self.errors: list[tuple[str, str]] = []
        self.quit_called = False
        self.destroyed = False

    def title(self, text: str) -> None:
        """Accept the window title."""

    def resizable(self, width: bool, height: bool) -> None:
        """Accept window sizing options."""

    def minsize(self, width: int, height: int) -> None:
        """Record the minimum window dimensions."""
        self.minimum_size = (width, height)

    def protocol(self, name: str, callback: Callable[[], None]) -> None:
        """Store the window-close handler."""
        assert name == "WM_DELETE_WINDOW"
        self.close_callback = callback

    def after(self, delay: int, callback: Callable[[], None]) -> None:
        """Queue a listener-health check for explicit execution."""
        assert delay > 0
        self.scheduled.append(callback)

    def mainloop(self) -> None:
        """Execute the test's UI actions."""
        self.on_mainloop()

    def close(self) -> None:
        """Request shutdown through the registered window-close handler."""
        assert self.close_callback is not None
        self.close_callback()

    def quit(self) -> None:
        """End the event loop while leaving widgets available for cleanup."""
        self.quit_called = True

    def destroy(self) -> None:
        """Record that window resources were released."""
        self.destroyed = True


@pytest.fixture
def controls(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[_FakeWindow, list[_FakeListener], _FakeOutlet]:
    """Replace the GUI, keyboard hook, and outlet with controlled fakes."""
    window = _FakeWindow()
    listeners: list[_FakeListener] = []
    outlet = _FakeOutlet()

    def listener_factory(
        *,
        on_press: Callable[[object], None],
        on_release: Callable[[object], None],
    ) -> _FakeListener:
        listener = _FakeListener(on_press=on_press, on_release=on_release)
        listeners.append(listener)
        return listener

    def window_factory() -> _FakeWindow:
        assert len(listeners) == 1
        assert listeners[0].ready
        return window

    def showerror(title: str, message: str, *, parent: _FakeWindow) -> None:
        assert parent is window
        window.errors.append((title, message))

    pynput = ModuleType("pynput")
    pynput.keyboard = SimpleNamespace(Listener=listener_factory)  # type: ignore[attr-defined]
    tkinter = ModuleType("tkinter")
    tkinter.Tk = window_factory  # type: ignore[attr-defined]
    tkinter.ttk = SimpleNamespace(  # type: ignore[attr-defined]
        Button=_FakeButton, Label=_FakeLabel
    )
    tkinter.messagebox = SimpleNamespace(showerror=showerror)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pynput", pynput)
    monkeypatch.setitem(sys.modules, "tkinter", tkinter)
    monkeypatch.setattr(utils, "build_stream_info", lambda: object())
    monkeypatch.setattr(key_lsl, "StreamOutlet", lambda _: outlet)
    return window, listeners, outlet


def test_main_window_label_and_size(
    controls: tuple[_FakeWindow, list[_FakeListener], _FakeOutlet],
) -> None:
    """Show a descriptive label in a wider control window."""
    window, _, _ = controls

    key_lsl.main()

    assert window.label is not None
    assert window.label.text == "Keyboard Logging & LSL Streaming"
    assert window.minimum_size == (400, 140)


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


@pytest.mark.parametrize("stop_before_close", [False, True])
def test_main_publishes_press_and_release(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    controls: tuple[_FakeWindow, list[_FakeListener], _FakeOutlet],
    stop_before_close: bool,
) -> None:
    """Toggle recording repeatedly and treat Escape as an ordinary key."""
    window, listeners, outlet = controls
    letter_key = SimpleNamespace(char="a")
    escape_key = SimpleNamespace(char=None, name="esc")
    later_key = SimpleNamespace(char="b")

    stream_info = object()
    build_stream_info_calls: list[None] = []
    outlet_factory_calls: list[object] = []

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
    monkeypatch.setattr(utils, "local_clock", iter(range(1, 9)).__next__)
    monkeypatch.setattr(utils.time, "time", lambda: 100.0)

    def exercise_controls() -> None:
        assert len(listeners) == 1
        listener = listeners[0]
        assert listener.ready
        assert listener.running
        listener.on_press(letter_key)
        listener.on_release(letter_key)
        assert not outlet.samples
        assert window.button is not None
        button = window.button
        assert button.text == "Start"

        button.command()
        assert button.text == "Stop"
        assert len(listeners) == 1
        assert listener.running
        window.scheduled.pop(0)()
        assert listener.stop_calls == 0

        for key in (letter_key, escape_key, later_key):
            assert listener.on_press(key) is None
            listener.on_release(key)
        assert listener.running

        button.command()
        assert button.text == "Start"
        assert listener.running
        assert listener.stop_calls == listener.join_calls == 0
        listener.on_press(letter_key)
        listener.on_release(letter_key)
        assert len(outlet.samples) == 6
        assert not window.destroyed
        assert not window.quit_called

        button.command()
        assert button.text == "Stop"
        assert len(listeners) == 1
        listener.on_press(letter_key)
        listener.on_release(letter_key)

        if stop_before_close:
            button.command()
            assert button.text == "Start"
            assert listener.running
        window.close()

    window.on_mainloop = exercise_controls
    key_lsl.main()

    assert window.quit_called
    assert window.destroyed
    assert all(not listener.running for listener in listeners)
    assert all(
        listener.stop_calls == listener.join_calls == 1 for listener in listeners
    )
    assert build_stream_info_calls == [None]
    assert outlet_factory_calls == [stream_info]
    assert [
        (json.loads(sample[0]), timestamp) for sample, timestamp in outlet.samples
    ] == [
        ({"event": "press", "key": "a", "time_unix": 100.0}, 1.0),
        ({"event": "release", "key": "a", "time_unix": 100.0}, 2.0),
        ({"event": "press", "key": "esc", "time_unix": 100.0}, 3.0),
        ({"event": "release", "key": "esc", "time_unix": 100.0}, 4.0),
        ({"event": "press", "key": "b", "time_unix": 100.0}, 5.0),
        ({"event": "release", "key": "b", "time_unix": 100.0}, 6.0),
        ({"event": "press", "key": "a", "time_unix": 100.0}, 7.0),
        ({"event": "release", "key": "a", "time_unix": 100.0}, 8.0),
    ]

    output = capsys.readouterr().out
    assert "Broadcasting on LSL stream: 'KeyboardEvents'" in output
    assert output.count("Stopping stream...") == 2
    assert "ESC to stop" not in output


def test_main_closes_without_recording(
    controls: tuple[_FakeWindow, list[_FakeListener], _FakeOutlet],
) -> None:
    """Allow closing the idle window without publishing keyboard events."""
    window, listeners, outlet = controls

    key_lsl.main()

    assert window.quit_called
    assert window.destroyed
    assert len(listeners) == 1
    assert not listeners[0].running
    assert listeners[0].stop_calls == listeners[0].join_calls == 1
    assert not outlet.samples


def test_main_cleans_up_after_ui_failure(
    controls: tuple[_FakeWindow, list[_FakeListener], _FakeOutlet],
) -> None:
    """Release the active listener and window when the event loop fails."""
    window, listeners, _ = controls

    def fail_mainloop() -> None:
        assert window.button is not None
        window.button.command()
        raise RuntimeError("UI failed")

    window.on_mainloop = fail_mainloop

    with pytest.raises(RuntimeError, match="UI failed"):
        key_lsl.main()

    assert window.destroyed
    assert not listeners[0].running
    assert listeners[0].stop_calls == listeners[0].join_calls == 1


def test_main_cleans_up_after_window_creation_failure(
    monkeypatch: pytest.MonkeyPatch,
    controls: tuple[_FakeWindow, list[_FakeListener], _FakeOutlet],
) -> None:
    """Release the initialized hook if the control window cannot be created."""
    window, listeners, _ = controls

    def fail_window() -> _FakeWindow:
        assert listeners[0].ready
        raise RuntimeError("Window creation failed")

    monkeypatch.setattr(sys.modules["tkinter"], "Tk", fail_window)

    with pytest.raises(RuntimeError, match="Window creation failed"):
        key_lsl.main()

    assert not window.destroyed
    assert not listeners[0].running
    assert listeners[0].stop_calls == listeners[0].join_calls == 1


def test_main_reports_listener_exit_before_start(
    controls: tuple[_FakeWindow, list[_FakeListener], _FakeOutlet],
) -> None:
    """Reject recording with a dead hook and show the failure only once."""
    window, listeners, outlet = controls

    def start_failed_listener() -> None:
        assert window.button is not None
        listeners[0].running = False
        window.button.command()
        assert window.button.state == "disabled"
        assert window.button.text == "Start"
        assert window.quit_called
        window.scheduled.pop(0)()
        assert len(window.errors) == 1

    window.on_mainloop = start_failed_listener
    key_lsl.main()

    assert window.destroyed
    assert not outlet.samples
    assert listeners[0].stop_calls == listeners[0].join_calls == 1


def test_main_surfaces_listener_failure(
    controls: tuple[_FakeWindow, list[_FakeListener], _FakeOutlet],
) -> None:
    """Show a visible error and surface the callback failure on shutdown."""
    window, listeners, _ = controls

    def fail_listener() -> None:
        assert window.button is not None
        button = window.button
        button.command()
        listeners[0].running = False
        listeners[0].error = RuntimeError("Publishing failed")

        window.scheduled.pop(0)()

        assert button.text == "Start"
        assert button.state == "disabled"
        assert len(window.errors) == 1
        assert window.errors[0][0] == "Keyboard capture stopped"
        assert window.quit_called

    window.on_mainloop = fail_listener
    with pytest.raises(RuntimeError, match="Publishing failed"):
        key_lsl.main()

    assert window.destroyed
    assert all(
        listener.stop_calls == listener.join_calls == 1 for listener in listeners
    )


def test_main_destroys_window_after_shutdown_failure(
    controls: tuple[_FakeWindow, list[_FakeListener], _FakeOutlet],
) -> None:
    """Destroy the window even if joining the listener raises an error."""
    window, listeners, _ = controls

    def close_failed_listener() -> None:
        assert window.button is not None
        window.button.command()
        listeners[0].error = RuntimeError("Listener failed")
        window.close()

    window.on_mainloop = close_failed_listener

    with pytest.raises(RuntimeError, match="Listener failed"):
        key_lsl.main()

    assert window.destroyed
    assert not listeners[0].running
    assert listeners[0].stop_calls == listeners[0].join_calls == 1
