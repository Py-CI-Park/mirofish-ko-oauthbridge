import os
import subprocess
import unittest
from pathlib import Path


class ConfigEnvPrecedenceTest(unittest.TestCase):
    def setUp(self):
        self.backend_dir = Path(__file__).resolve().parents[1]
        self.python_exe = self.backend_dir / ".venv" / "Scripts" / "python.exe"
        self.project_root = self.backend_dir.parent
        self.env_local_path = self.project_root / ".env.local"
        self.original_env_local = (
            self.env_local_path.read_text(encoding="utf-8")
            if self.env_local_path.exists()
            else None
        )

    def tearDown(self):
        if self.original_env_local is None:
            if self.env_local_path.exists():
                self.env_local_path.unlink()
        else:
            self.env_local_path.write_text(self.original_env_local, encoding="utf-8")

    def test_runtime_env_overrides_dotenv_defaults(self):
        env = os.environ.copy()
        env["LLM_BASE_URL"] = "http://127.0.0.1:8788/v1"

        proc = subprocess.run(
            [
                str(self.python_exe),
                "-c",
                "from app.config import Config; print(Config.LLM_BASE_URL)",
            ],
            cwd=self.backend_dir,
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )

        self.assertEqual(proc.stdout.strip(), "http://127.0.0.1:8788/v1")

    def test_dotenv_local_overrides_dotenv_defaults_when_runtime_env_is_absent(self):
        self.env_local_path.write_text(
            "LLM_BASE_URL=http://127.0.0.1:8799/v1\n",
            encoding="utf-8",
        )
        env = os.environ.copy()
        env.pop("LLM_BASE_URL", None)

        proc = subprocess.run(
            [
                str(self.python_exe),
                "-c",
                "from app.config import Config; print(Config.LLM_BASE_URL)",
            ],
            cwd=self.backend_dir,
            capture_output=True,
            text=True,
            env=env,
            check=True,
        )

        self.assertEqual(proc.stdout.strip(), "http://127.0.0.1:8799/v1")


if __name__ == "__main__":
    unittest.main()
