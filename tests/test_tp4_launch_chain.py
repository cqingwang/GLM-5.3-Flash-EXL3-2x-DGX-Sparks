#!/usr/bin/env python3
"""CPU-only regressions for the TP4 direct-asset and lifecycle contract."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
START = ROOT / "start-tp4.sh"
STOP = ROOT / "stop.sh"


def _base_env(home: Path, **extra: str) -> dict[str, str]:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(home),
        "USER": "tp4-test",
        "LC_ALL": "C",
    }
    env.update(extra)
    return env


def _write_tp4_fixture(tmp_path: Path, *, target_weights: bool, dflash_weights: bool) -> tuple[Path, Path]:
    module = tmp_path / "glm53"
    module.mkdir()
    shutil.copy2(START, module / "start-tp4.sh")
    target = tmp_path / "models" / "Mia-AiLab" / "GLM-5.3-Flash-exl3-4bpw-ablit"
    dflash = tmp_path / "models" / "incoai" / "GLM-5.3-Flash-DFlash2"
    target.mkdir(parents=True)
    dflash.mkdir(parents=True)
    (target / "config.json").write_text("{}\n", encoding="utf-8")
    (dflash / "config.json").write_text("{}\n", encoding="utf-8")
    if target_weights:
        (target / "model-00001-of-00001.safetensors").touch()
    if dflash_weights:
        (dflash / "model.safetensors").touch()

    (module / ".env").write_text(
        f"MODEL_PATH={target}\n"
        f"MODEL_ROOT={tmp_path / 'models'}\n"
        f"DFLASH_MODEL_PATH={dflash}\n"
        "SPEC_METHOD=dflash\n"
        "SKIP_DOWNLOAD=1\n"
        "SKIP_SYNC=1\n",
        encoding="utf-8",
    )
    (module / ".env.tp4").write_text("\n", encoding="utf-8")
    return module, target


def test_tp4_direct_download_rejects_missing_target_weights(tmp_path: Path) -> None:
    module, _ = _write_tp4_fixture(tmp_path, target_weights=False, dflash_weights=True)
    result = subprocess.run(
        ["bash", "start-tp4.sh", "download"],
        cwd=module,
        env=_base_env(tmp_path / "home"),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "safetensors" in result.stderr


def test_tp4_direct_download_rejects_missing_dflash_weights(tmp_path: Path) -> None:
    module, target = _write_tp4_fixture(tmp_path, target_weights=True, dflash_weights=False)
    result = subprocess.run(
        ["bash", "start-tp4.sh", "download"],
        cwd=module,
        env=_base_env(tmp_path / "home"),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "DFlash2" in result.stderr
    assert str(target) not in result.stderr


def _write_stop_fixture(tmp_path: Path, *, tp4_head_running: bool) -> tuple[Path, Path]:
    module = tmp_path / "stop-fixture"
    module.mkdir()
    shutil.copy2(STOP, module / "stop.sh")
    record = tmp_path / "stop-record"
    for name in ("start.sh", "start-tp3.sh", "start-tp4.sh"):
        launcher = module / name
        launcher.write_text(
            "#!/usr/bin/env bash\n"
            "printf '%s %s\\n' \"$(basename \"$0\")\" \"$*\" >> \"$STOP_RECORD\"\n",
            encoding="utf-8",
        )
        launcher.chmod(0o755)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker = bin_dir / "docker"
    docker.write_text(
        "#!/usr/bin/env bash\n"
        "if [ \"$1\" = inspect ] && [ \"$2\" = glm53-exl3-tp4-head ]; then\n"
        f"  {'exit 0' if tp4_head_running else 'exit 1'}\n"
        "fi\n"
        "exit 1\n",
        encoding="utf-8",
    )
    docker.chmod(0o755)
    return module, record


def test_stop_dispatches_explicit_tp4_to_all_ranks(tmp_path: Path) -> None:
    module, record = _write_stop_fixture(tmp_path, tp4_head_running=False)
    result = subprocess.run(
        ["bash", "stop.sh", "tp4"],
        cwd=module,
        env=_base_env(tmp_path / "home", PATH=f"{tmp_path / 'bin'}:/usr/bin:/bin", STOP_RECORD=str(record)),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert record.read_text(encoding="utf-8").splitlines() == ["start-tp4.sh stop"]


def test_stop_auto_detects_running_tp4_head(tmp_path: Path) -> None:
    module, record = _write_stop_fixture(tmp_path, tp4_head_running=True)
    result = subprocess.run(
        ["bash", "stop.sh"],
        cwd=module,
        env=_base_env(tmp_path / "home", PATH=f"{tmp_path / 'bin'}:/usr/bin:/bin", STOP_RECORD=str(record)),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert record.read_text(encoding="utf-8").splitlines() == ["start-tp4.sh stop"]
