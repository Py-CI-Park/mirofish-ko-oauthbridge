import os
import subprocess
import sys
import unittest
from pathlib import Path


class ConfigEnvPrecedenceTest(unittest.TestCase):
    def test_runtime_env_overrides_dotenv_defaults(self):
        backend_dir = Path(__file__).resolve().parents[1]
        python_exe = backend_dir / ".venv" / "Scripts" / "python.exe"
        env = os.environ.copy()
        env["LLM_BASE_URL"] = "http://127.0.0.1:8788/v1"

        proc = subprocess.run(
            [
                str(python_exe),
                "-c",
                "from app.config import Config; print(Config.LLM_BASE_URL)",
            ],
            cwd=backend_dir,
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )

        self.assertEqual(proc.stdout.strip(), "http://127.0.0.1:8788/v1")


if __name__ == "__main__":
    unittest.main()
