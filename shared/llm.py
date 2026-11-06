#!/usr/bin/env python3
"""The model client: one request per prompt, answers handed back as they arrive, so a run can stop and go on.

Backends (CLAUDE_BACKEND):
  cli  (default) every request goes through the `claude` CLI on the user's subscription (claude.ai login; no API key reaches it).
       The cost figures are the CLI's list-price estimate ("list USD"): recorded, not spent.
  api  the Anthropic API through Message Batches (half price), key read from $ANTHROPIC_KEY_FILE, never printed and never
       exported. A cap in USD is checked before a batch is sent. (Ported from the research client, where it ran; not re-run here.)

CLAUDE_MODEL (default claude-opus-5-5), CLAUDE_CLI_WORKERS (default 1: requests at a time on the subscription).

    . ./env.sh; python3 shared/llm.py smoke"""
import json, os, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor, as_completed

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")
# USD per million tokens: input, output, cache read, cache write (5 min)
PRICE = {"claude-opus-5-5": (4.00, 20.00, 0.20, 5.00), "claude-fable-5-1": (10.00, 50.00, 0.25, 12.50),
         "claude-sonnet-5-5": (2.00, 10.00, 0.20, 2.50), "claude-haiku-5-5": (0.10, 0.50, 0.01, 0.125)}
BACKEND = os.environ.get("CLAUDE_BACKEND", "cli")
WORKERS = int(os.environ.get("CLAUDE_CLI_WORKERS", "1"))
MAX_TOKENS = 6000


def _cli_env():
    drop = ("ANTHROPIC_API_KEY", "CLAUDECODE", "CLAUDE_EFFORT")
    return {k: v for k, v in os.environ.items() if k not in drop and not k.startswith("CLAUDE_CODE_") and k != "CLAUDE_PID"}


def cli_one(prompt, system, model=MODEL, effort="medium", schema=None, timeout=1800, tries=2):
    """one request through `claude -p` (no tools, no settings, no MCP, no project notes: run in an empty directory) ->
    {"ok", "text", "stop", "list_usd", "usage"} or {"ok": False, "error"}"""
    cmd = ["claude", "-p", "--model", model, "--effort", effort, "--tools", "", "--strict-mcp-config", "--setting-sources", "",
           "--no-session-persistence", "--system-prompt", system, "--output-format", "json"]
    if schema:
        cmd += ["--json-schema", json.dumps(schema)]
    err = None
    for _ in range(tries):
        with tempfile.TemporaryDirectory() as d:
            try:
                p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, cwd=d, env=_cli_env(), timeout=timeout)
                o = json.loads(p.stdout)
            except (subprocess.TimeoutExpired, ValueError) as e:
                err = str(e)[:200]; continue
        if o.get("is_error"):
            err = (o.get("result") or o.get("subtype") or "error")[:200]; continue
        text = json.dumps(o["structured_output"], ensure_ascii=False) if o.get("structured_output") is not None else o.get("result", "")
        u = o.get("usage", {})
        return {"ok": True, "text": text, "stop": "end_turn" if o.get("subtype") == "success" else o.get("subtype"),
                "list_usd": o.get("total_cost_usd", 0.0), "usage": {k: u.get(k, 0) for k in ("input_tokens", "output_tokens",
                                                                                             "cache_read_input_tokens", "cache_creation_input_tokens")}}
    return {"ok": False, "error": err}


def _api_client():
    import anthropic
    path = os.environ.get("ANTHROPIC_KEY_FILE")
    if not path or not os.path.exists(path):
        sys.exit("ANTHROPIC_KEY_FILE not set or missing (. ./env.sh)")
    with open(path, encoding="utf-8") as f:
        key = f.read().strip()
    return anthropic.Anthropic(api_key=key)


def estimate(prompts, model=MODEL, out_tokens=2500):
    """a batch's cost in USD, estimated from the prompts' lengths (three characters a token)"""
    pi, po, _, _ = PRICE[model]
    return sum(len(p) / 3 * pi + out_tokens * po for p in prompts) / 1e6 / 2


def _api_batch(items, system, model, effort, schema, state):
    """items through one Message Batch; state = a dict kept by the caller (the batch id survives a stop). Yields (id, result)"""
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request
    cl = _api_client()
    if not state.get("batch"):
        cfg = {"effort": effort}
        if schema:
            cfg["format"] = {"type": "json_schema", "schema": schema}
        reqs = [Request(custom_id=i, params=MessageCreateParamsNonStreaming(
            model=model, max_tokens=MAX_TOKENS, output_config=cfg,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": p}])) for i, p in items]
        state["batch"] = cl.messages.batches.create(requests=reqs).id; state["save"]()
    while cl.messages.batches.retrieve(state["batch"]).processing_status != "ended":
        time.sleep(30)
    pi, po, pr, pw = PRICE[model]
    for r in cl.messages.batches.results(state["batch"]):
        if r.result.type != "succeeded":
            yield r.custom_id, {"ok": False, "error": r.result.type}; continue
        m = r.result.message; u = m.usage
        usd = (u.input_tokens * pi + u.output_tokens * po + (u.cache_read_input_tokens or 0) * pr + (u.cache_creation_input_tokens or 0) * pw) / 1e6 / 2
        yield r.custom_id, {"ok": True, "text": next((x.text for x in m.content if x.type == "text"), ""), "stop": m.stop_reason, "usd": usd,
                            "usage": {"input_tokens": u.input_tokens, "output_tokens": u.output_tokens}}
    state["batch"] = None; state["save"]()


def run(items, system, schema=None, model=MODEL, effort="medium", state=None):
    """items [(id, prompt)] -> yields (id, result) as each answer arrives. cli: WORKERS at a time; api: one batch (state keeps its id)"""
    if BACKEND == "api":
        yield from _api_batch(items, system, model, effort, schema, state if state is not None else {"save": lambda: None})
        return
    with ThreadPoolExecutor(WORKERS) as ex:
        fut = {ex.submit(cli_one, p, system, model, effort, schema): i for i, p in items}
        for f in as_completed(fut):
            yield fut[f], f.result()


if __name__ == "__main__":
    if sys.argv[1:] != ["smoke"]:
        sys.exit(__doc__)
    if BACKEND != "cli":
        sys.exit("the smoke test runs on the cli backend only (it must not spend)")
    r = cli_one("Reply with the single word: ready", "Answer briefly.", MODEL, "low")
    print(f"backend cli  model {MODEL}  ", {k: r.get(k) for k in ("ok", "text", "stop", "list_usd", "error")})
