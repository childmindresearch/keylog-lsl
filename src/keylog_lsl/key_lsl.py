"""Publish keyboard markers to LSL.

This module captures global key presses and releases and writes them to one
LSL marker stream named ``KeyboardEvents``. A single Start/Stop button controls
capture; closing the control window exits the application.

Each marker is JSON with:
- ``event``: ``press`` or ``release``
- ``key``: normalized key name
- ``time_unix``: wall-clock Unix timestamp

LSL sample timestamps are set with ``pylsl.local_clock()`` at callback time.
This gives an ``(lsl_time, time_unix)`` pair for each event, which is useful
for post-hoc alignment with non-LSL logs such as browser UI timestamps.
"""

from threading import Lock

from pylsl import StreamOutlet

from keylog_lsl import utils


def main() -> None:
    """Open a single-button window to start and stop keyboard capture.

    Initialize the listener before Tk because macOS keyboard-layout initialization
    can abort the process after the GUI gains focus. Keep that listener alive and
    gate marker publishing instead of restarting it.
    """
    import tkinter as tk
    from tkinter import messagebox, ttk

    from pynput import keyboard

    outlet = StreamOutlet(utils.build_stream_info())
    recording = False
    recording_lock = Lock()

    def on_press(key: object) -> None:
        """Publish each key press, including Escape."""
        with recording_lock:
            if recording:
                utils.push_marker(outlet, "press", key)

    def on_release(key: object) -> None:
        """Publish each key release received from the listener."""
        with recording_lock:
            if recording:
                utils.push_marker(outlet, "release", key)

    def stop_recording() -> None:
        """Finish any in-flight marker and ignore subsequent keyboard events."""
        nonlocal recording
        with recording_lock:
            was_recording = recording
            recording = False
        if was_recording:
            print("Stopping stream...")

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()
    try:
        listener.wait()
        window = tk.Tk()
        try:
            listener_failed = False

            def check_listener() -> None:
                """Notify the user if the keyboard hook stops unexpectedly."""
                nonlocal listener_failed
                if listener_failed:
                    return
                if not listener.is_alive():
                    listener_failed = True
                    stop_recording()
                    button.configure(text="Start", state="disabled")
                    messagebox.showerror(
                        "Keyboard capture stopped",
                        "The keyboard listener stopped unexpectedly. Check the "
                        "terminal for details and verify keyboard-monitoring "
                        "permissions, then restart the application.",
                        parent=window,
                    )
                    window.quit()
                else:
                    window.after(100, check_listener)

            def toggle_stream() -> None:
                """Pause or resume publishing without restarting the listener."""
                nonlocal recording
                if not listener.is_alive():
                    check_listener()
                    return
                if recording:
                    stop_recording()
                    button.configure(text="Start")
                else:
                    with recording_lock:
                        recording = True
                    button.configure(text="Stop")
                    print("Listening for keystrokes... (Click Stop to pause)")

            window.title("LSL Keyboard Event Streamer")
            window.minsize(400, 140)
            window.resizable(False, False)
            label = ttk.Label(window, text="Keyboard Logging -> LSL")
            label.pack(padx=32, pady=(24, 0))
            button = ttk.Button(window, text="Start", command=toggle_stream, width=16)
            button.pack(padx=32, pady=24)
            window.protocol("WM_DELETE_WINDOW", window.quit)
            window.after(100, check_listener)

            print("--- LSL Keyboard Event Streamer ---")
            print("Broadcasting on LSL stream: 'KeyboardEvents'")
            print('Marker payload: JSON with fields "event", "key", "time_unix"')
            print("Click Start in the control window to begin; close it to exit.")
            window.mainloop()
        finally:
            stop_recording()
            window.destroy()
    finally:
        listener.stop()
        listener.join()


if __name__ == "__main__":  # pragma: no cover
    main()
