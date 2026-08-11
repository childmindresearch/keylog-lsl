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

## Quick start

Start the keyboard stream publisher:

```sh
uv run keylog-lsl
```

This opens an LSL stream named `KeyboardEvents` with JSON markers such as:

```json
{"event":"press","key":"a","time_unix":1760000000.1234}
```

Press `ESC` to stop.

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
