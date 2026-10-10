"""Portable equivalent of `make build` for Windows hosts without GNU Make."""
import shutil
import subprocess
import sys
import os
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    # No recursive deletion: overwrite owned build artifacts in the workspace.
    layer = ROOT / "build/layer/python"
    layer.mkdir(parents=True, exist_ok=True)
    for module in ("model", "scheduler", "sources", "backend", "forecasting", "assistant"):
        shutil.copytree(ROOT / module, layer / module, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (layer / "data").mkdir(exist_ok=True)
    shutil.copy2(ROOT / "data/regions.yaml", layer / "data/regions.yaml")
    shutil.copy2(ROOT / "functions/worker/app.py", layer / "worker_inline.py")
    flags = ["--platform", "manylinux2014_x86_64", "--implementation", "cp", "--python-version", "3.12", "--only-binary=:all:"]
    subprocess.run([sys.executable, "-m", "pip", "install", "--target", str(layer), *flags, "pyyaml>=6"], check=True, cwd=ROOT)
    assistant = ROOT / "build/assistant-layer/python"
    assistant.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        # pip --platform does not change sys_platform dependency markers.
        # Resolve the existing assistant's Linux dependencies inside Python 3.12.
        # Stage on Linux and transfer one archive: pip's thousands of moves over
        # a Windows Docker bind mount are prohibitively slow, especially OneDrive.
        code = ("import subprocess,sys,tarfile; "
                "subprocess.run([sys.executable,'-m','pip','install','--no-compile','--target','/tmp/tidewise-assistant','--only-binary=:all:','-r','/workspace/requirements-assistant.txt'],check=True); "
                "archive=tarfile.open('/workspace/build/assistant-layer.tar.gz','w:gz'); "
                "archive.add('/tmp/tidewise-assistant',arcname='python'); archive.close()")
        subprocess.run(["docker", "run", "--rm", "--entrypoint", "python", "-v", f"{ROOT}:/workspace",
                        "public.ecr.aws/lambda/python:3.12", "-c", code], check=True, cwd=ROOT)
        with tarfile.open(ROOT / "build/assistant-layer.tar.gz") as archive:
            archive.extractall(assistant.parent, filter="data")
        interpreter = subprocess.check_output(["py", "-3.12", "-c", "import sys; print(sys.executable)"], text=True).strip()
        os.environ["PATH"] = str(Path(interpreter).parent) + os.pathsep + os.environ["PATH"]
    else:
        subprocess.run([sys.executable, "-m", "pip", "install", "--target", str(assistant), *flags, "-r", "requirements-assistant.txt"], check=True, cwd=ROOT)
    subprocess.run([sys.executable, "-m", "samcli", "build"], check=True, cwd=ROOT)


if __name__ == "__main__":
    main()
