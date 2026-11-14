"""Behavior of the desktop `read_terminal` bridge tool.

The pane itself lives in the renderer; this tool is the schema + dispatch half.
What matters here is the contract the model is given back:

* a populated pane passes through untouched,
* a blank pane says why it is blank (a shell nobody typed into is NOT evidence
  that command execution is broken — that misreading made a whole release look
  dead),
* a missing bridge, bad args, or a throwing callback fail loudly.
"""

import json

from tools.read_terminal_tool import read_terminal_tool


def _pane(**overrides):
    payload = {
        "cursor_row": 0,
        "end": 0,
        "start": 0,
        "text": "",
        "total_lines": 0,
        "viewport_rows": 24,
    }
    payload.update(overrides)

    return json.dumps(payload)


def test_passes_the_renderer_payload_through():
    raw = _pane(end=3, text="PS C:\\Users\\dev> python --version\r\nPython 3.11.9", total_lines=3)

    result = json.loads(read_terminal_tool(callback=lambda **_: raw))

    assert result["text"].endswith("Python 3.11.9")
    assert result["total_lines"] == 3
    assert "note" not in result


def test_blank_pane_explains_where_command_output_lives():
    result = json.loads(read_terminal_tool(callback=lambda **_: _pane()))

    assert result["text"] == ""
    assert "terminal" in result["note"]


def test_forwards_the_requested_window():
    seen = {}

    def callback(**window):
        seen.update(window)

        return _pane(text="line")

    read_terminal_tool(start_line=40, count=10, callback=callback)

    assert seen == {"start": 40, "count": 10}


def test_negative_start_clamps_to_zero_and_count_has_a_floor():
    seen = {}
    read_terminal_tool(start_line=-5, count=0, callback=lambda **window: seen.update(window) or _pane())

    assert seen == {"start": 0, "count": 1}


def test_rejects_non_integer_window():
    result = json.loads(read_terminal_tool(start_line="nope", callback=lambda **_: _pane()))

    assert "integers" in result["error"]


def test_missing_callback_reports_desktop_only():
    result = json.loads(read_terminal_tool())

    assert "desktop" in result["error"]


def test_empty_answer_is_an_error_not_an_empty_pane():
    result = json.loads(read_terminal_tool(callback=lambda **_: ""))

    assert "No in-app terminal is open" in result["error"]


def test_callback_failure_is_reported():
    def callback(**_):
        raise RuntimeError("renderer went away")

    result = json.loads(read_terminal_tool(callback=callback))

    assert "renderer went away" in result["error"]
