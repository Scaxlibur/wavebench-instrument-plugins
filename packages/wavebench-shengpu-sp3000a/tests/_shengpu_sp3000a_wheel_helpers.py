from __future__ import annotations

import os
import shutil
from pathlib import Path
import subprocess
import sysconfig

import wavebench


def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=True)


def _write_isolated_runtime_bridge(*, purelib: Path, workspace: Path) -> None:
    bridge = workspace / "runtime-bridge"
    bridge.mkdir()
    for source in Path(sysconfig.get_paths()["purelib"]).iterdir():
        name = source.name
        if (
            name.startswith("wavebench")
            or name == "pip"
            or name.endswith((".dist-info", ".egg-info", ".pth", ".egg"))
        ):
            continue
        try:
            os.symlink(source, bridge / name, target_is_directory=source.is_dir())
        except OSError:
            if source.is_dir():
                shutil.copytree(source, bridge / name)
            else:
                shutil.copy2(source, bridge / name)
    Path(purelib, "wavebench-test-runtime.pth").write_text(
        str(Path(wavebench.__file__).resolve().parents[1]) + "\n" + str(bridge) + "\n",
        encoding="utf-8",
    )
