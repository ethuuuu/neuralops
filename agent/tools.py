"""Tool registry. A tool is a plain Python function plus a schema."""
from pathlib import Path
from core import trace
from .tools_impl import sandbox, docgen

WORKSPACE = Path(__file__).resolve().parent.parent / "workspace"

TOOLS = {}


def tool(name, description, params):
    def deco(fn):
        TOOLS[name] = {"fn": fn, "description": description, "params": params}
        return fn
    return deco


@tool("read_file", "Read a text file from the workspace.", {"path": "relative path"})
def read_file(path):
    p = (WORKSPACE / path).resolve()
    if WORKSPACE.resolve() not in p.parents and p != WORKSPACE.resolve():
        return {"error": "path escapes workspace"}
    return {"content": p.read_text(errors="ignore")[:20000]}


@tool("write_file", "Write a text file into the workspace.",
      {"path": "relative path", "content": "file contents"})
def write_file(path, content):
    p = WORKSPACE / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return {"written": str(p), "bytes": len(content)}


@tool("search_knowledge_base",
      "Search the organisation's manuals, SOPs and past correspondence.",
      {"query": "what to look for"})
def search_kb(query):
    from kb import index
    store = getattr(search_kb, "_store", None)
    if store is None:
        store = index.load()
        search_kb._store = store
    return {"results": index.search(store, query, k=4)}


@tool("run_python", "Execute Python in an isolated sandbox and return output.",
      {"code": "python source"})
def run_python(code):
    return sandbox.run_python(code)


@tool("create_approval_note", "Produce a formatted Word approval note.",
      {"title": "str", "reference": "str", "background": "str",
       "findings": "list of {item, observation, severity}",
       "recommendation": "str"})
def create_approval_note(title, reference, background, findings, recommendation):
    return {"file": docgen.approval_note(title, reference, background,
                                         findings, recommendation)}


def describe():
    return "\n".join(
        f"- {n}({', '.join(t['params'])}): {t['description']}"
        for n, t in TOOLS.items()
    )


def call(name, args):
    if name not in TOOLS:
        return {"error": f"unknown tool '{name}'. Available: {list(TOOLS)}"}
    trace.emit("tool_call", tool=name, args=args)
    try:
        result = TOOLS[name]["fn"](**args)
    except Exception as e:
        result = {"error": f"{type(e).__name__}: {e}"}
    trace.emit("tool_result", tool=name, result=str(result)[:600])
    return result
