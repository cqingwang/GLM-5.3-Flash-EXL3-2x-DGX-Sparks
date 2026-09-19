#!/usr/bin/env bash
set -euo pipefail

# Receive one docker-save stream, load it locally, and forward the same stream
# to the next management node. The FIFO prevents the local docker load from
# competing with the forwarder for stdin.
next_target="${1:-}"
next_next_target="${2:-}"
image_ref="${3:?missing image reference}"
case "$image_ref" in
    *"'"*) echo "image reference contains an unsupported quote" >&2; exit 2 ;;
esac

work_dir="$(mktemp -d /tmp/glm53-image-ring.XXXXXX)"
fifo_path="$work_dir/image.tar"
load_log="$work_dir/docker-load.log"
mkfifo "$fifo_path"
cleanup() { rm -rf "$work_dir"; }
trap cleanup EXIT

docker load <"$fifo_path" >"$load_log" 2>&1 &
loader_pid=$!

if [ -n "$next_target" ]; then
    set +e
    tee "$fifo_path" | ssh -T -o BatchMode=yes -o ConnectTimeout=15 \
        -o StrictHostKeyChecking=accept-new "$next_target" \
        "/opt/spark/glm53_flash_exl3/scripts/ring_docker_load.sh '$next_next_target' '' '$image_ref'"
    pipeline_status=("${PIPESTATUS[@]}")
    tee_status="${pipeline_status[0]}"
    forward_status="${pipeline_status[1]}"
    set -e
else
    set +e
    tee "$fifo_path" >/dev/null
    tee_status="$?"
    forward_status=0
    set -e
fi

set +e
wait "$loader_pid"
load_status="$?"
set -e
if [ "$load_status" -ne 0 ]; then
    cat "$load_log" >&2
fi

[ "$tee_status" -eq 0 ] && [ "$forward_status" -eq 0 ] && [ "$load_status" -eq 0 ]
