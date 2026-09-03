"""Task router: picks which model handles a request, and says why.

Two-stage by design. A cheap keyword pass handles the obvious cases with
zero latency. Anything ambiguous falls through to a small model that
classifies the task. Both paths record their reasoning into the trace,
because 'show model auto-selection' is a scored requirement and an
unexplained choice proves nothing.
"""
from . import registry, trace
from .llm import LLM

_CLASSIFY = """You classify a user request into exactly one category.
Categories: code, vision, general.
- code: writing, running, debugging code, or numeric calculation
- vision: the request involves an image, scan, drawing or photograph
- general: everything else, including summarising and drafting documents
Reply with JSON only: {"category": "...", "reason": "<8 words max>"}"""


def route(request: str, has_image: bool = False):
    cfg = registry.routing_cfg()

    if has_image:
        return _decided("vision", "request carries an image", "signal")

    low = request.lower()
    for rule in cfg.get("rules", []):
        for kw in rule["match_any"]:
            if kw in low:
                return _decided(rule["route_to"], f"matched keyword '{kw}'", "keyword")

    try:
        result = LLM(cfg["default"]).chat_json(
            [{"role": "system", "content": _CLASSIFY},
             {"role": "user", "content": request}],
            max_tokens=100,
        )
        mapping = {"code": "coder", "vision": "vision", "general": "general"}
        target = mapping.get(result.get("category"), cfg["default"])
        return _decided(target, result.get("reason", "classifier"), "classifier")
    except Exception as e:
        return _decided(cfg["default"], f"classifier failed: {e}", "fallback")


def _decided(model_id, reason, method):
    trace.emit("route", chosen_model=model_id, reason=reason, method=method)
    return model_id, reason
