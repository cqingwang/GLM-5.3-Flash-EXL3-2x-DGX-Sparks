#!/usr/bin/env python3
"""GLM TP4 管理配置回归检查，不连接远程节点。"""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]
CONFIG = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
ENGINE = CONFIG["engines"]["glm53_flash_exl3"]
LAUNCHER = (ROOT / "glm53_flash_exl3" / "start-tp4.sh").read_text(encoding="utf-8")

assert ENGINE["start"] == "start-tp4.sh start"
assert ENGINE["env_file"] == ".env.tp4"
assert ENGINE["tensor_parallel_size"] == 4
assert ENGINE["nnodes"] == 4
assert CONFIG["common"]["worker_nodes"] == ["spark-c", "spark-d", "spark-b"]
assert "MODEL_PATH_MODE=direct" in LAUNCHER
assert 'MODEL_ROOT:$CONTAINER_MODEL_ROOT:ro' in LAUNCHER
assert 'NCCL_ALGO=$NCCL_ALGO' in LAUNCHER
assert 'NCCL_SOCKET_IFNAME="$HEAD_SOCKET_IFACE"' in LAUNCHER
assert 'WORKER2_SSH' in LAUNCHER
assert 'NCCL_IB_PEER_HCA' in LAUNCHER
assert LAUNCHER.count('2) printf \'%s\' "$WORKER2_SSH"') == 1

print("managed GLM TP4 config tests: PASS")
