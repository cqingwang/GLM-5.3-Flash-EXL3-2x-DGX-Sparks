#!/usr/bin/env bash
# stop.sh — stop the GLM-5.3-Flash EXL3 vLLM server(s)
#
# Stops whichever stack is running (both, if both exist). Names and SSH
# come from the launchers: TP=2 via start.sh (.env), TP=3 via start-tp3.sh
# (.env then .env.tp3), and TP=4 via start-tp4.sh (.env then .env.tp4), so
# rank-specific fabric/user pins are not duplicated here.
#   TP=2  glm53-exl3-head + glm53-exl3-worker
#   TP=3  glm53-exl3-tp3-head + glm53-exl3-tp3-w1 + glm53-exl3-tp3-w2
#   TP=4  glm53-exl3-tp4-head + glm53-exl3-tp4-w1 + glm53-exl3-tp4-w2 + glm53-exl3-tp4-w3
# Weights and compile caches stay on disk so a later start restarts fast.
#
# Usage:
#   ./stop.sh           stop the running stack(s). Local heads are detected;
#                       if no head is here, all configured launchers still run
#                       so orphaned workers are removed.
#   ./stop.sh tp2       TP=2 only  (./start.sh stop)
#   ./stop.sh tp3       TP=3 only  (./start-tp3.sh stop)
#   ./stop.sh tp4       TP=4 only  (./start-tp4.sh stop)
#   ./stop.sh all       all stacks, skip detection
#
# Equivalent to ./start.sh stop, ./start-tp3.sh stop and/or ./start-tp4.sh stop.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    sed -n '2,/^set -euo pipefail/p' "${BASH_SOURCE[0]}" \
        | sed -e '/^set -euo pipefail/d' -e 's/^# \{0,1\}//'
}

have_container() {
    docker inspect "$1" >/dev/null 2>&1
}

# Names from the same files the launchers source. TP=2 never reads .env.tp3.
# Subshell so .env does not leak into start.sh as "caller overrides".
tp2_head_name() {
    (
        CONTAINER_HEAD="glm53-exl3-head"
        if [ -f "$SCRIPT_DIR/.env" ]; then
            set -a
            # shellcheck disable=SC1091
            source "$SCRIPT_DIR/.env"
            set +a
        fi
        printf '%s' "${CONTAINER_HEAD:-glm53-exl3-head}"
    )
}

tp3_head_name() {
    (
        CONTAINER_HEAD="glm53-exl3-tp3-head"
        if [ -f "$SCRIPT_DIR/.env" ]; then
            set -a
            # shellcheck disable=SC1091
            source "$SCRIPT_DIR/.env"
            set +a
        fi
        if [ -f "$SCRIPT_DIR/.env.tp3" ]; then
            set -a
            # shellcheck disable=SC1091
            source "$SCRIPT_DIR/.env.tp3"
            set +a
        fi
        printf '%s' "${CONTAINER_HEAD:-glm53-exl3-tp3-head}"
    )
}

tp4_head_name() {
    (
        CONTAINER_HEAD="glm53-exl3-tp4-head"
        if [ -f "$SCRIPT_DIR/.env" ]; then
            set -a
            # shellcheck disable=SC1091
            source "$SCRIPT_DIR/.env"
            set +a
        fi
        if [ -f "$SCRIPT_DIR/.env.tp4" ]; then
            set -a
            # shellcheck disable=SC1091
            source "$SCRIPT_DIR/.env.tp4"
            set +a
        fi
        printf '%s' "${CONTAINER_HEAD:-glm53-exl3-tp4-head}"
    )
}

stop_tp2() {
    "$SCRIPT_DIR/start.sh" stop
}

stop_tp3() {
    "$SCRIPT_DIR/start-tp3.sh" stop
}

stop_tp4() {
    "$SCRIPT_DIR/start-tp4.sh" stop
}

want_tp2=0
want_tp3=0
want_tp4=0
cmd="${1:-}"
case "$cmd" in
    "" )
        if have_container "$(tp2_head_name)"; then want_tp2=1; fi
        if have_container "$(tp3_head_name)"; then want_tp3=1; fi
        if have_container "$(tp4_head_name)"; then want_tp4=1; fi
        if [ "$want_tp2" = 0 ] && [ "$want_tp3" = 0 ] && [ "$want_tp4" = 0 ]; then
            # Neither head is local — still tear down workers so a removed
            # head cannot leave workers up. Skip a topology if it was never
            # configured (avoids copying an example env during stop).
            want_tp2=1
            if [ -f "$SCRIPT_DIR/start-tp3.sh" ] && [ -f "$SCRIPT_DIR/.env.tp3" ]; then
                want_tp3=1
            fi
            if [ -f "$SCRIPT_DIR/start-tp4.sh" ] && [ -f "$SCRIPT_DIR/.env.tp4" ]; then
                want_tp4=1
            fi
        fi
        ;;
    tp2|2) want_tp2=1 ;;
    tp3|3)
        want_tp3=1
        ;;
    tp4|4)
        want_tp4=1
        ;;
    all)
        want_tp2=1
        want_tp3=1
        want_tp4=1
        ;;
    -h|--help|help) usage; exit 0 ;;
    *)
        echo "unknown argument: $cmd (try ./stop.sh --help)" >&2
        exit 1
        ;;
esac

rc=0
if [ "$want_tp2" = 1 ]; then
    stop_tp2 || rc=$?
fi
if [ "$want_tp3" = 1 ]; then
    if [ ! -f "$SCRIPT_DIR/start-tp3.sh" ]; then
        echo "ERROR: start-tp3.sh not found" >&2
        rc=1
    else
        stop_tp3 || rc=$?
    fi
fi
if [ "$want_tp4" = 1 ]; then
    if [ ! -f "$SCRIPT_DIR/start-tp4.sh" ]; then
        echo "ERROR: start-tp4.sh not found" >&2
        rc=1
    else
        stop_tp4 || rc=$?
    fi
fi
exit "$rc"
