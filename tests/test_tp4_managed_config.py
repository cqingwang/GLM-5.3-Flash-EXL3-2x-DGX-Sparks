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
assert ENGINE["gpu_mem_util"] == 0.75
assert ENGINE["max_num_seqs"] == 8
assert ENGINE["max_num_batched_tokens"] == 2048
assert ENGINE["dflash_tokens"] == 3
assert ENGINE["mixed_prefill_chunk"] == "off"
assert CONFIG["common"]["worker_nodes"] == ["spark-c", "spark-d", "spark-b"]
assert "MODEL_PATH_MODE=direct" in LAUNCHER
assert 'MODEL_ROOT:$CONTAINER_MODEL_ROOT:ro' in LAUNCHER
assert 'NCCL_ALGO=$NCCL_ALGO' in LAUNCHER
assert 'NCCL_SOCKET_IFNAME="$HEAD_SOCKET_IFACE"' in LAUNCHER
assert 'WORKER2_SSH' in LAUNCHER
assert 'NCCL_IB_PEER_HCA' in LAUNCHER
assert LAUNCHER.count('2) printf \'%s\' "$WORKER2_SSH"') == 1

DEPLOY = (ROOT / "deploy.sh").read_text(encoding="utf-8")
assert '"GPU_MEM_UTIL=$gpu_mem_util"' in DEPLOY
assert '"MAX_NUM_SEQS=$engine_max_num_seqs"' in DEPLOY
assert '"MAX_NUM_BATCHED_TOKENS=$engine_max_num_batched_tokens"' in DEPLOY
assert '"DFLASH_TOKENS=$dflash_tokens"' in DEPLOY
assert '"GLM53_MIXED_PREFILL_CHUNK=$mixed_prefill_chunk"' in DEPLOY

print("managed GLM TP4 config tests: PASS")
