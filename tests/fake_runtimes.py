"""Stand-in `claude` and `codex` binaries for tests that run real agent turns without a model.

`path_with(directory)` writes both executables and returns a PATH that finds them first. Behaviour comes from
environment variables: FAKE_STATUS (qk-result status, or `none` for no block), FAKE_PROMPT (file that receives the
prompt), FAKE_TOOL (a tool name the Claude stand-in calls first), FAKE_WRITE (file name to create in the working
directory), FAKE_SLEEP (seconds), FAKE_BARRIER (directory: wait until two turns have started) and FAKE_EXIT.
"""

import gc
import os
from pathlib import Path
import sys
import warnings


COMMON = r'''
import json, os, sys, time
from pathlib import Path

prompt = sys.stdin.read()
if os.environ.get("FAKE_PROMPT"):
    Path(os.environ["FAKE_PROMPT"]).write_text(prompt)
if os.environ.get("FAKE_WRITE"):
    Path(os.environ["FAKE_WRITE"]).write_text("made by the agent\n")
barrier = os.environ.get("FAKE_BARRIER")
alone = False
if barrier:
    (Path(barrier) / str(os.getpid())).write_text("")
    deadline = time.time() + 20
    while len(list(Path(barrier).iterdir())) < 2 and time.time() < deadline:
        time.sleep(0.02)
    alone = len(list(Path(barrier).iterdir())) < 2
time.sleep(float(os.environ.get("FAKE_SLEEP", "0")))
status = os.environ.get("FAKE_STATUS", "done")
text = "cwd=%s alone=%s home=%s\n" % (Path.cwd().name, alone, os.environ.get("HOME", ""))
if status != "none":
    text += "```qk-result\n" + json.dumps({"status": status, "summary": "fake turn", "files": [], "evidence": [],
                                           "reason": "" if status == "done" else "fake reason",
                                           "findings": []}) + "\n```"

def emit(event):
    print(json.dumps(event), flush=True)
'''

CLAUDE = COMMON + r'''
tool = os.environ.get("FAKE_TOOL")
if tool:
    emit({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": tool, "input": {}}]}})
    time.sleep(0.2)
emit({"type": "result", "result": text, "total_cost_usd": 0.25,
      "usage": {"input_tokens": 10, "cache_read_input_tokens": 4, "cache_creation_input_tokens": 1,
                "output_tokens": 7}})
sys.exit(int(os.environ.get("FAKE_EXIT", "0")))
'''

CODEX = COMMON + r'''
argv = sys.argv[1:]
Path(argv[argv.index("--output-last-message") + 1]).write_text(text)
emit({"type": "turn.completed", "usage": {"input_tokens": 20, "cached_input_tokens": 5, "output_tokens": 3}})
sys.exit(int(os.environ.get("FAKE_EXIT", "0")))
'''


def collect_pipes():
    """Finalize a finished turn's pipe objects now, so their warnings do not land in a later test's captured stderr."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ResourceWarning)
        gc.collect()


def path_with(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for name, body in (("claude", CLAUDE), ("codex", CODEX)):
        path = directory / name
        path.write_text("#!%s\n%s" % (sys.executable, body))
        path.chmod(0o755)
    return str(directory) + os.pathsep + os.environ.get("PATH", "")
