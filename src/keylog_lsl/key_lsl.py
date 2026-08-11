"""Publish keyboard markers to LSL.

This module captures global key presses and releases and writes them to one
LSL marker stream named ``KeyboardEvents``.

Each marker is JSON with:
- ``event``: ``press`` or ``release``
- ``key``: normalized key name
- ``time_unix``: wall-clock Unix timestamp

LSL sample timestamps are set with ``pylsl.local_clock()`` at callback time.
This gives an ``(lsl_time, time_unix)`` pair for each event, which is useful
for post-hoc alignment with non-LSL logs such as browser UI timestamps.
"""

from pylsl import StreamOutlet

from keylog_lsl import utils


def main() -> None:
    """Create an LSL outlet and listen for keyboard events until ``ESC``.

    The listener invokes local callbacks for each key press and release. Returning
    False from the press callback stops the listener when ``ESC`` is pressed.
    """
    from pynput import keyboard

    outlet: StreamOutlet

    def on_press(key: object) -> bool | None:
        """Publish each key press received from the listener and stop it on Escape."""
        utils.push_marker(outlet, "press", key)

        if key == keyboard.Key.esc:
            print("Stopping stream...")
            return False
        return None

    def on_release(key: object) -> None:
        """Publish each key release received from the listener."""
        utils.push_marker(outlet, "release", key)

    info = utils.build_stream_info()

    outlet = StreamOutlet(info)

    print("--- LSL Keyboard Event Streamer ---")
    print("Broadcasting on LSL stream: 'KeyboardEvents'")
    print('Marker payload: JSON with fields "event", "key", "time_unix"')
    print("Listening for keystrokes... (Press ESC to stop)")

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()


if __name__ == "__main__":  # pragma: no cover
    main()
