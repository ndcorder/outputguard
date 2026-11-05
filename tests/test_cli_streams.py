import json
import os
import subprocess
import sys
import time

import pytest

from benchmarks.check_cli_parity import PYTHON_ENTRY


def test_cli_waits_for_chunked_utf8_input_and_preserves_crlf(tmp_path):
    schema = tmp_path / "schema.json"
    schema.write_text("true")
    text = '{\r\n"value":"😀λ"\r\n}\r\n'
    command = [sys.executable, "-c", PYTHON_ENTRY, "validate", "-", "-s", str(schema), "-fjson"]
    with subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ) as process:
        for byte in text.encode("utf-8"):
            process.stdin.write(bytes([byte]))
            process.stdin.flush()
            time.sleep(0.001)
        process.stdin.close()
        process.stdin = None
        stdout, stderr = process.communicate(timeout=20)
    assert process.returncode == 0 and not stderr
    result = json.loads(stdout)
    assert result["valid"] and result["data"] == {"value": "😀λ"}
    assert result["original_text"] == text


@pytest.mark.skipif(os.name == "nt", reason="POSIX broken pipe semantics")
def test_cli_broken_output_pipe_exits_cleanly():
    command = [sys.executable, "-c", PYTHON_ENTRY, "repair", "-", "-fjson"]
    with subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ) as process:
        process.stdout.close()
        process.stdout = None
        _, stderr = process.communicate(json.dumps({"value": "x" * 200000}).encode(), timeout=20)
    assert process.returncode == 1, stderr
    assert b"Traceback" not in stderr and b"Exception ignored" not in stderr
