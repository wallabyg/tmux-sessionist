"""Run with: python3 -m unittest discover -s tests -v"""

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")


class FzfTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sessionist-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.bin = self.directory / "bin"
        self.bin.mkdir()
        self.log = self.directory / "calls"
        self.env = dict(os.environ, PATH=str(self.bin), CALL_LOG=str(self.log))
        # Only these utilities are needed by the entry point. Omitting fzf
        # from this private PATH tests absence even on machines with it installed.
        for name in ("dirname", "grep"):
            (self.bin / name).symlink_to(shutil.which(name))
        self.executable("tmux", '''
import json, os, sys
args = sys.argv[1:]
with open(os.environ["CALL_LOG"], "a") as log:
    log.write(json.dumps(args) + "\\n")
command = args[0]
if command == "show-option":
    print(os.environ.get({"@sessionist-fzf": "ENABLED",
                          "@sessionist-fzf-target": "MODE"}.get(args[-1], ""), ""))
elif command == "list-commands":
    print("display-popup (popup)" if not os.environ.get("OLD_TMUX") else "run-shell (run)")
elif command == "display-message":
    print("/dev/pts/42")
elif command == "display-popup":
    sys.exit(int(os.environ.get("POPUP_STATUS", "0")))
elif command in ("list-sessions", "list-windows"):
    print(os.environ.get("CANDIDATES", "$7\\twork space (2 windows)"))
''')

    def executable(self, name, body):
        path = self.bin / name
        path.write_text("#!" + shutil.which("python3") + "\n" + body)
        path.chmod(0o755)

    def fzf(self):
        self.executable("fzf", '''
import os, sys
data = sys.stdin.read()
with open(os.environ["CALL_LOG"], "a") as log:
    import json
    log.write(json.dumps(["fzf"] + sys.argv[1:]) + "\\n")
sys.stdout.write(os.environ.get("SELECTION", data.splitlines()[0] if data else ""))
sys.exit(int(os.environ.get("FZF_STATUS", "0")))
''')

    def run_script(self, name, *args, **env):
        subprocess.run([BASH, str(ROOT / "scripts" / name), *args],
                       env=dict(self.env, **env), check=True, capture_output=True)
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def assert_fallback(self, calls):
        self.assertTrue(any(call[0] == "run-shell" for call in calls))
        self.assertTrue(any(call[:3] == ["command", "-p", "session:"] for call in calls))

    def test_missing_fzf(self):
        self.assert_fallback(self.run_script("goto_session.sh"))

    def test_disabled(self):
        self.fzf()
        calls = self.run_script("goto_session.sh", ENABLED="off")
        self.assert_fallback(calls)
        self.assertFalse(any(call[0] == "display-popup" for call in calls))

    def test_old_tmux(self):
        self.fzf()
        self.assert_fallback(self.run_script("goto_session.sh", OLD_TMUX="1"))

    def test_popup_failure(self):
        self.fzf()
        self.assert_fallback(self.run_script("goto_session.sh", POPUP_STATUS="1"))

    def test_popup_client_and_shell_quoting(self):
        self.fzf()
        client = "/dev/pts/client's terminal"
        calls = self.run_script("goto_session.sh", client)
        popup = next(call for call in calls if call[0] == "display-popup")
        self.assertEqual(popup[1:3], ["-c", client])
        self.assertEqual(shlex.split(popup[-1]),
                         ["bash", str(ROOT / "scripts/fzf_session.sh"), client])
        self.assertFalse(any(call[0] == "command" for call in calls))

    def test_session_id_and_client(self):
        self.fzf()
        calls = self.run_script("fzf_session.sh", "/dev/pts/42")
        self.assertEqual(calls[-1], ["switch-client", "-c", "/dev/pts/42", "-t", "$7"])

    def test_window_id_and_session(self):
        self.fzf()
        calls = self.run_script("fzf_session.sh", "/dev/pts/42", MODE="windows",
                                CANDIDATES="$9:@12\twork space:3: editor's window")
        self.assertEqual(calls[-2], ["select-window", "-t", "$9:@12"])
        self.assertEqual(calls[-1], ["switch-client", "-c", "/dev/pts/42", "-t", "$9"])

    def test_cancel_empty_and_invalid_selection(self):
        self.fzf()
        for env in ({"FZF_STATUS": "130"}, {"SELECTION": ""},
                    {"SELECTION": "a query\n$7\twork"}):
            with self.subTest(env=env):
                self.log.unlink(missing_ok=True)
                calls = self.run_script("fzf_session.sh", "/dev/pts/42", **env)
                self.assertFalse(any(call[0] in ("switch-client", "select-window")
                                     for call in calls))

    @unittest.skipUnless(shutil.which("fzf"), "fzf is not installed")
    def test_real_fzf_matches_names_and_preserves_ids(self):
        real_fzf = shutil.which("fzf")
        self.executable("fzf", f'''
import os, sys
os.execv({real_fzf!r}, [{real_fzf!r}, "--filter=beta", *sys.argv[1:]])
''')
        # Global defaults must not open a nested popup or change the output.
        calls = self.run_script("fzf_session.sh", "/dev/pts/42",
                                CANDIDATES="$7\talpha project\n$9\tbeta project",
                                FZF_DEFAULT_OPTS="--filter=alpha --print-query --expect=enter --popup",
                                FZF_DEFAULT_OPTS_FILE="")
        self.assertEqual(calls[-1], ["switch-client", "-c", "/dev/pts/42", "-t", "$9"])


if __name__ == "__main__":
    unittest.main()
