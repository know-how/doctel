import os
import shutil
import subprocess
import sys


def _find_npm_executable() -> str | None:
  npm_executable = shutil.which("npm") or shutil.which("npm.cmd")
  if npm_executable:
    return npm_executable
  candidates = [
    r"C:\Program Files\nodejs\npm.cmd",
    r"C:\Program Files\nodejs\npm",
    r"C:\Program Files (x86)\nodejs\npm.cmd",
    r"C:\Program Files (x86)\nodejs\npm",
  ]
  for candidate in candidates:
    if os.path.exists(candidate):
      return candidate
  return None


def main() -> None:
  root_dir = os.path.dirname(os.path.abspath(__file__))
  frontend_dir = os.path.join(root_dir, "frontend")

  env = os.environ.copy()
  env.setdefault("VITE_API_BASE_URL", "http://localhost:8000")

  npm_executable = _find_npm_executable()
  frontend_proc = None
  if npm_executable is None:
    print(
      "npm was not found on PATH. Starting backend only. "
      "Install Node.js and ensure `npm` is available to run the frontend.",
      file=sys.stderr,
    )
  else:
    npm_dir = os.path.dirname(npm_executable)
    if npm_dir and env.get("PATH") and npm_dir not in env["PATH"]:
      env["PATH"] = npm_dir + os.pathsep + env["PATH"]
    frontend_proc = subprocess.Popen(
      [npm_executable, "run", "dev", "--", "--host", "0.0.0.0"],
      cwd=frontend_dir,
      env=env,
    )

  try:
    import uvicorn

  except ImportError:
    if frontend_proc:
      frontend_proc.terminate()
      try:
        frontend_proc.wait(timeout=10)
      except Exception:
        pass
    print(
      "uvicorn is not installed. Install backend dependencies with "
      "`python -m pip install -r requirements.txt` and run again.",
      file=sys.stderr,
    )
    sys.exit(1)

  try:
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
  finally:
    if frontend_proc:
      frontend_proc.terminate()
      try:
        frontend_proc.wait(timeout=10)
      except Exception:
        pass


if __name__ == "__main__":
  main()
