"""Backend-agnostic model client.

Every model is reached over the OpenAI /v1/chat/completions dialect.
MLX, Ollama, llama.cpp and vLLM all speak it. Application code never
imports a model library directly, so porting from a Mac to the
customer's NVIDIA server is a config change.
"""
import json, time
import httpx
from . import registry, trace


class LLM:
    def __init__(self, model_id: str):
        self.model_id = model_id
        self.cfg = registry.model(model_id)
        self.client = httpx.Client(timeout=300)

    def chat(self, messages, temperature=0.2, max_tokens=2048, json_mode=False):
        body = {
            "model": self.cfg["model_name"],
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}

        t0 = time.time()
        r = self.client.post(f"{self.cfg['base_url']}/chat/completions", json=body)
        r.raise_for_status()
        data = r.json()
        text = data["choices"][0]["message"]["content"]

        trace.emit(
            "inference",
            model_id=self.model_id,
            model_name=self.cfg["model_name"],
            latency_s=round(time.time() - t0, 2),
            prompt_chars=sum(len(m["content"]) for m in messages if isinstance(m.get("content"), str)),
            output_chars=len(text),
        )
        return text

    def chat_json(self, messages, **kw):
        """Ask for JSON and parse it defensively. Local models add stray prose."""
        raw = self.chat(messages, json_mode=True, **kw)
        return _parse_json(raw)


def _parse_json(raw: str):
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("```")[1]
        if s.startswith("json"):
            s = s[4:]
    start = s.find("{")
    end = s.rfind("}")
    if start == -1 or end == -1:
        trace.emit("json_parse_failed", raw=raw[:400])
        raise ValueError(f"No JSON object in model output: {raw[:200]}")
    return json.loads(s[start : end + 1])


def embed(texts):
    """Embed a list of strings. Must be the SAME model at index and query time."""
    cfg = registry.embeddings_cfg()
    out = []
    with httpx.Client(timeout=120) as c:
        for t in texts:
            r = c.post(
                f"{cfg['base_url']}/api/embeddings",
                json={"model": cfg["model_name"], "prompt": t},
            )
            r.raise_for_status()
            out.append(r.json()["embedding"])
    trace.emit("embed", model=cfg["model_name"], count=len(texts))
    return out
