"""Run the sparkDash Code decode benchmark against the local vLLM endpoint."""

import json
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

import requests


ENV_PATH = "/opt/spark/glm53_flash_exl3/.env.tp4"
BASE_URL = "http://127.0.0.1:8888/v1/chat/completions"
MODEL = "Mia-AiLab/GLM-5.3-Flash-exl3-4bpw-ablit"
PROMPT = """Output only Python source code. No comments, no docstrings, no markdown fences.
Write functions clamp_00 through clamp_49. Each function is exactly:
def clamp_NN(x, lo=0, hi=1):
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x
Change only the function name suffix (00, 01, … 49). One blank line between functions. No other text."""


def read_api_key() -> str:
    for line in open(ENV_PATH, encoding="utf-8"):
        if line.startswith("VLLM_API_KEY="):
            return line.split("=", 1)[1].strip().strip("'\"")
    raise RuntimeError("VLLM_API_KEY is missing")


def request(prompt: str, max_tokens: int) -> dict:
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "top_p": 1,
        "max_tokens": max_tokens,
        "min_tokens": max_tokens,
        "ignore_eos": True,
        "stop": [],
        "stream": True,
        "stream_options": {"include_usage": True},
        "chat_template_kwargs": {"enable_thinking": False},
    }
    headers = {
        "Authorization": f"Bearer {read_api_key()}",
        "Content-Type": "application/json",
    }
    started = time.perf_counter()
    first_token = None
    last_token = None
    text_chars = 0
    usage = None
    error = ""
    try:
        with requests.post(
            BASE_URL,
            headers=headers,
            json=body,
            stream=True,
            timeout=(30, 240),
        ) as response:
            if response.status_code != 200:
                return {"ok": False, "status": response.status_code, "error": response.text[:500]}
            for raw in response.iter_lines(decode_unicode=True):
                if not raw or not raw.startswith("data:"):
                    continue
                payload = raw[5:].strip()
                if payload == "[DONE]":
                    continue
                try:
                    item = json.loads(payload)
                except json.JSONDecodeError:
                    continue
                if "error" in item:
                    error = str(item["error"])
                    continue
                if item.get("usage"):
                    usage = item["usage"]
                choices = item.get("choices") or []
                if choices:
                    delta = (choices[0].get("delta") or {}).get("content")
                    if delta:
                        if first_token is None:
                            first_token = time.perf_counter()
                        last_token = time.perf_counter()
                        text_chars += len(delta)
    except Exception as exc:  # noqa: BLE001 - benchmark reports request failures inline.
        return {"ok": False, "error": repr(exc)}

    completion_tokens = (usage or {}).get("completion_tokens", text_chars)
    decode_seconds = (
        last_token - first_token
        if first_token is not None and last_token is not None
        else None
    )
    return {
        "ok": True,
        "ttft": first_token - started if first_token is not None else None,
        "decode": decode_seconds,
        "tokens": completion_tokens,
        "chars": text_chars,
        "usage": usage,
        "error": error,
    }


def benchmark_cell(concurrency: int, repetition: int) -> dict:
    warmup = request(f"{PROMPT}\nWarmup only.", 32)
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(
                request,
                f"{PROMPT}\n(stream {index + 1}/{concurrency})",
                512,
            )
            for index in range(concurrency)
        ]
        items = [future.result() for future in futures]
    good = [
        item
        for item in items
        if item.get("ok") and item.get("tokens") == 512 and item.get("decode")
    ]
    aggregate = (
        sum(item["tokens"] for item in good) / max(item["decode"] for item in good)
        if good
        else None
    )
    stream = (
        statistics.mean(item["tokens"] / item["decode"] for item in good)
        if good
        else None
    )
    ttft = statistics.mean(item["ttft"] for item in good) if good else None
    result = {
        "conc": concurrency,
        "rep": repetition,
        "warmup_ok": warmup.get("ok"),
        "good": len(good),
        "aggregate": aggregate,
        "stream": stream,
        "ttft": ttft,
        "wall": time.perf_counter() - started,
        "items": items,
    }
    print(json.dumps({key: result[key] for key in ("conc", "rep", "good", "aggregate", "stream", "ttft", "wall")}), flush=True)
    return result


def main() -> None:
    rows = [
        benchmark_cell(concurrency, repetition)
        for concurrency in (1, 2, 4)
        for repetition in (1, 2, 3)
    ]
    for concurrency in (1, 2, 4):
        complete = [
            row for row in rows if row["conc"] == concurrency and row["good"] == concurrency
        ]
        print(
            "SUMMARY",
            json.dumps(
                {
                    "conc": concurrency,
                    "agg_median": statistics.median(row["aggregate"] for row in complete)
                    if complete
                    else None,
                    "stream_median": statistics.median(row["stream"] for row in complete)
                    if complete
                    else None,
                    "ttft_median": statistics.median(row["ttft"] for row in complete)
                    if complete
                    else None,
                    "tokens": [[item.get("tokens") for item in row["items"]] for row in complete],
                }
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
