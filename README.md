# keylog-lsl

[![Build](https://github.com/childmindresearch/keylog-lsl/actions/workflows/test.yaml/badge.svg?branch=main)](https://github.com/childmindresearch/keylog-lsl/actions/workflows/test.yaml?query=branch%3Amain)
[![codecov](https://codecov.io/gh/childmindresearch/keylog-lsl/branch/main/graph/badge.svg)](https://codecov.io/gh/childmindresearch/keylog-lsl)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
![stability-experimental](https://img.shields.io/badge/stability-experimental-orange.svg)
[![LGPL-2.1 License](https://img.shields.io/badge/license-LGPL--2.1-blue.svg)](https://github.com/childmindresearch/keylog-lsl/blob/main/LICENSE)
[![pages](https://img.shields.io/badge/api-docs-blue)](https://childmindresearch.github.io/keylog-lsl)

A Python tool for publishing global keyboard events over Lab Streaming Layer
(LSL).

## Features

- Publishes key press and release events to a `KeyboardEvents` LSL stream.
- Stores normalized key names and wall-clock timestamps in JSON markers.
- Provides a small control window with one Start/Stop button.

## Installation

This project requires Python 3.12 or newer and
[uv](https://docs.astral.sh/uv/).

```sh
git clone https://github.com/childmindresearch/keylog-lsl.git
cd keylog-lsl
uv sync
```

On macOS, grant the terminal or Python process Accessibility permission when
prompted so `pynput` can monitor global keyboard events.

The control window requires Tkinter and a desktop display. If your Python
installation does not include Tkinter, install Tk support for that interpreter
(for example, `python-tk@3.13` for Homebrew Python 3.13 or `python3-tk` on
Debian/Ubuntu).

## Quick start

Start the keyboard stream publisher:

```sh
uv run keylog-lsl
```

This opens a small control window, initially stopped. Click **Start** to publish
keyboard events, then click the same button, now labeled **Stop**, to stop
recording. Click **Start** again to resume on the same `KeyboardEvents` LSL
stream, with JSON markers such as:

```json
{"event":"press","key":"a","time_unix":1760000000.1234}
```

`ESC` is recorded like any other key; it does not stop recording or exit.
Close the control window to stop any active recording and exit.

The keyboard hook is initialized before the window opens for macOS compatibility.
While stopped, keyboard events are ignored and no markers are sent.

## Development

```sh
uv sync --all-groups
uv run pre-commit install
uv run pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for pull request requirements.

## Links

- [API documentation](https://childmindresearch.github.io/keylog-lsl)
- [Lab Streaming Layer](https://labstreaminglayer.org/)
