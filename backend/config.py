"""
Central configuration loader.

Reads the project's `config.yaml` and copies its values into the process
environment, so all the existing `os.getenv(...)` reads scattered across the
backend keep working without any change. This must be imported *before* the
service modules (llm, embedding, compliance_judge, ...) so their module-level
`os.getenv(...)` constants pick up the file values.

Precedence (highest first):
    1. A real environment variable already set (e.g. by run.sh or a promptfoo
       per-instance `LLM_MODEL=...`) — the file never overrides these.
    2. The value in config.yaml.
    3. The hard-coded default in the code that reads the variable.

So the config file is the single knob for day-to-day tuning, while explicit
env vars still win when you need to override one instance (e.g. running two
backends with different models for a comparison).

Config file location, in order:
    - $QMS_CONFIG_PATH (if set)
    - <project root>/config.yaml   (the parent of this backend/ folder)
    - <backend>/config.yaml
"""
import os
import sys

# Friendly YAML key (dotted) -> the environment variable the code actually reads.
# Keep this in sync with the `os.getenv(...)` calls in the backend.
_KEY_TO_ENV = {
    # models
    "models.chat": "LLM_MODEL",
    "models.compliance": "COMPLIANCE_MODEL",
    "models.embedding": "EMBEDDING_MODEL_NAME",
    # corpus — which document module the checker/traceability read. Retrieval is
    # switched separately via retrieval.collection.
    "corpus.module": "CORPUS_MODULE",
    "corpus.drafts_module": "DRAFTS_MODULE",
    # retrieval
    "retrieval.top_k": "CHAT_TOP_K",
    "retrieval.relevance_threshold": "RAG_RELEVANCE_THRESHOLD",
    "retrieval.context_turns": "CHAT_RETRIEVAL_CONTEXT_TURNS",
    "retrieval.late_chunking": "LATE_CHUNKING",
    "retrieval.collection": "CHAT_COLLECTION",
    # generation
    "generation.num_ctx": "LLM_NUM_CTX",
    "generation.num_predict": "LLM_NUM_PREDICT",
    "generation.keep_alive": "OLLAMA_KEEP_ALIVE",
    "generation.think": "LLM_THINK",
    # services
    "services.ollama_url": "OLLAMA_URL",
    "services.qdrant_url": "QDRANT_URL",
    # history
    "history.raw_cap": "CHAT_HISTORY_RAW_CAP",
    "history.user_turns": "CHAT_HISTORY_USER_TURNS",
    "history.assistant_turns": "CHAT_HISTORY_ASSISTANT_TURNS",
    "history.char_budget": "CHAT_HISTORY_CHAR_BUDGET",
    "history.msg_chars": "CHAT_HISTORY_MSG_CHARS",
    "history.db_path": "HISTORY_DB_PATH",
    # summary
    "summary.every_turns": "CHAT_SUMMARY_EVERY_TURNS",
    "summary.min_turns": "CHAT_SUMMARY_MIN_TURNS",
    "summary.max_chars": "CHAT_SUMMARY_MAX_CHARS",
    # compliance
    "compliance.judge_max_chars": "COMPLIANCE_JUDGE_MAX_CHARS",
    # logging
    "logging.log_prompts": "LOG_PROMPTS",
    "logging.prompt_log_path": "PROMPT_LOG_PATH",
    # uploads
    "uploads.max_bytes": "MAX_UPLOAD_BYTES",
}


def _candidate_paths():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    env_path = os.getenv("QMS_CONFIG_PATH")
    return [p for p in (env_path, os.path.join(root, "config.yaml"),
                        os.path.join(here, "config.yaml")) if p]


def _flatten(prefix, obj, out):
    """Flatten nested dict -> dotted keys. Leaves (scalars) become env values."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            _flatten(f"{prefix}.{k}" if prefix else k, v, out)
    else:
        out[prefix] = obj


def _to_env_str(value):
    """Render a YAML scalar as the string form the code expects."""
    if isinstance(value, bool):
        return "1" if value else "0"        # code reads "1"/"0"/"true"/"false"
    return str(value)


def load_config():
    """Load config.yaml into os.environ (without overriding real env vars).

    Returns the path loaded, or None if no file was found. Never raises: a
    missing file or missing PyYAML just means the code falls back to env/defaults.
    """
    try:
        import yaml
    except ImportError:
        return None

    path = next((p for p in _candidate_paths() if os.path.isfile(p)), None)
    if not path:
        return None

    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except Exception as exc:  # malformed YAML — don't take the server down
        print(f"[config] {path} okunamadı, varsayılanlar kullanılacak: {exc}",
              file=sys.stderr, flush=True)
        return None

    flat = {}
    _flatten("", data, flat)

    applied = 0
    for dotted, value in flat.items():
        env_key = _KEY_TO_ENV.get(dotted)
        if not env_key or value is None or value == "":
            continue  # unknown key or "leave default" (empty) — skip
        # setdefault: a real environment variable already set wins over the file.
        if env_key not in os.environ:
            os.environ[env_key] = _to_env_str(value)
            applied += 1

    # Diagnostic goes to stderr so `--print-env` stdout carries only export lines.
    print(f"[config] {path} yüklendi ({applied} ayar uygulandı).",
          file=sys.stderr, flush=True)
    return path


def resolved_env():
    """After load_config(), return {ENV_KEY: value} for every mapped variable
    that is currently set (from the file, a real env var, or a prior default)."""
    return {env: os.environ[env] for env in _KEY_TO_ENV.values() if env in os.environ}


# Load immediately on import so it happens before service modules read env vars.
load_config()


if __name__ == "__main__":
    # `python config.py --print-env` emits shell `export KEY='value'` lines for
    # the resolved settings, so run.sh can source config.yaml as the single
    # source of truth for QDRANT_URL / OLLAMA_URL / CHAT_COLLECTION etc.
    import sys
    import shlex
    if "--print-env" in sys.argv:
        for k, v in resolved_env().items():
            print(f"export {k}={shlex.quote(v)}")
