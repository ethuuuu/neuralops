"""The agent loop: plan, act, observe, repeat.

Tool calling is done through our own JSON protocol rather than the OpenAI
`tools` parameter, because native tool-call support across local backends
(MLX, llama.cpp, Ollama) is inconsistent and differs by model. A plain JSON
contract works on every backend and is easy to debug because you can read
exactly what the model emitted.

Two failure modes are handled explicitly, because both WILL happen:
  - the model repeats the same tool call forever  -> repetition break
  - the model emits prose instead of JSON         -> reprompt once, then stop
"""
import json
from core import trace
from core.llm import LLM
from core.router import route
from . import tools

SYSTEM = """You are an assistant operating entirely on an organisation's own
hardware. You have no internet access. Work step by step using tools.

Available tools:
{tools}

Reply with a single JSON object and nothing else, in one of two forms.

To use a tool:
{{"thought": "<one sentence>", "tool": "<name>", "args": {{...}}}}

When the task is complete:
{{"thought": "<one sentence>", "final": "<your answer for the user>"}}

Rules:
- Ground factual claims in tool results. If you did not retrieve it, say so.
- When you use knowledge base results, name the source document.
- Never invent file contents, measurements or reference numbers."""


def run(request: str, max_steps: int = 8, has_image: bool = False):
    model_id, reason = route(request, has_image=has_image)
    llm = LLM(model_id)

    messages = [
        {"role": "system", "content": SYSTEM.format(tools=tools.describe())},
        {"role": "user", "content": request},
    ]

    seen_calls = []
    for step in range(max_steps):
        trace.emit("step", n=step + 1, model=model_id)
        try:
            action = llm.chat_json(messages, max_tokens=1200)
        except ValueError:
            messages.append({"role": "user", "content":
                             "That was not valid JSON. Reply with one JSON object only."})
            try:
                action = llm.chat_json(messages, max_tokens=1200)
            except ValueError as e:
                trace.emit("abort", why="model would not produce JSON")
                return {"ok": False, "error": str(e), "steps": step + 1}

        if "final" in action:
            trace.emit("final", steps=step + 1)
            return {"ok": True, "answer": action["final"],
                    "steps": step + 1, "model": model_id, "route_reason": reason}

        name, args = action.get("tool"), action.get("args", {})
        signature = json.dumps([name, args], sort_keys=True)
        if seen_calls.count(signature) >= 2:
            trace.emit("abort", why="repeated identical tool call", tool=name)
            messages.append({"role": "user", "content":
                             "You have already made that exact call twice and got the "
                             "same result. Use a different approach or give your final answer."})
            seen_calls = []
            continue
        seen_calls.append(signature)

        result = tools.call(name, args)
        messages.append({"role": "assistant", "content": json.dumps(action)})
        messages.append({"role": "user", "content":
                         f"Tool result for {name}:\n{json.dumps(result, default=str)[:6000]}"})

    trace.emit("abort", why="step limit reached")
    return {"ok": False, "error": f"Did not finish within {max_steps} steps"}
