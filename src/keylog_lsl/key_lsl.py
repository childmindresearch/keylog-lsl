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

from pylsl import StreamOutlet, local_clock

from keylog_lsl import utils


def main() -> None:
    """Create the marker outlet and stream events until ``ESC``.

    The stream uses one irregular-rate string channel with type ``Markers``.
    Stream ``desc`` metadata documents the channel and JSON payload fields.
    """
    from pynput import keyboard

    info = utils.build_stream_info()

    outlet = StreamOutlet(info)

    print("--- LSL Keyboard Event Streamer ---")
    print("Broadcasting on LSL stream: 'KeyboardEvents'")
    print('Marker payload: JSON with fields "event", "key", "time_unix"')
    print("Listening for keystrokes... (Press ESC to stop)")

    def on_press(key: object) -> bool | None:
        """Push a press marker and stop the listener on Escape."""
        lsl_time = local_clock()
        marker = utils.make_marker("press", key)
        outlet.push_sample([marker], lsl_time)
        print(f"Pushed to LSL: {marker}")

        if key == keyboard.Key.esc:
            print("Stopping stream...")
            return False
        return None

    def on_release(key: object) -> None:
        """Push a release marker for the given key."""
        lsl_time = local_clock()
        marker = utils.make_marker("release", key)
        outlet.push_sample([marker], lsl_time)
        print(f"Pushed to LSL: {marker}")

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()


if __name__ == "__main__":  # pragma: no cover
    main()
