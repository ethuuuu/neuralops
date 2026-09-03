# Sovereign AI workbench — foundation scaffold

A thin end-to-end skeleton for the air-gapped industrial AI workbench. Everything
runs. Nothing is a placeholder that silently does nothing. Replace stubs one at a
time and the system stays working throughout.

## Why Python and not Rust

A request spends seconds in model inference, hundreds of milliseconds in OCR and
disk, and about a millisecond in orchestration code. Rust would optimise the
millisecond. Meanwhile the fast paths we depend on — tokenizers, BM25, vector
search, safetensors — are already Rust underneath, reached through Python
bindings. We get the speed where it exists and keep the ecosystem where it lives:
MLX, python-docx, python-pptx, openpyxl and the whole OCR stack are Python-only.

## Run it before you have any models

    pip install -r requirements.txt
    cd demo && python smoke_test.py

Four things pass with no model server running: the sandbox executes code, the
sandbox contains a crash, a Word approval note is produced, and the egress guard
blocks an outbound connection. Get this green on day one.

Then, with model servers up:

    python main.py "summarise the latest inspection report and draft an approval note"
    python main.py --proof

## Architecture

    config.yaml            model registry + routing rules. Adding a model = editing this.
    core/
      guard.py             egress guard — blocks and logs every outbound connection
      trace.py             structured log of every intermediate stage
      registry.py          reads config; the only module that knows what models exist
      llm.py               backend-agnostic client (OpenAI dialect) + embeddings
      router.py            picks the model per task, records why
    kb/
      chunk.py             structure-aware chunking
      index.py             hybrid retrieval (vector + BM25, rank-fused)
    agent/
      loop.py              plan / act / observe loop with JSON tool protocol
      tools.py             tool registry
      tools_impl/
        sandbox.py         isolated code execution
        docgen.py          Word deliverables
    main.py                entry point; installs the guard before anything else

## Five design decisions worth defending to a judge

**Every model is reached over an HTTP endpoint listed in config.** No application
code imports a model library. This is what makes "add new open-weight models
later without redesigning the system" true rather than aspirational, and it is
how the same code runs on a Mac in the demo and on the customer's NVIDIA server
in deployment. Change a URL, not a codebase.

**The router explains itself.** Cheap keyword matching handles obvious cases at
zero latency; ambiguous ones fall through to a small classifying model. Both
paths write their reasoning to the trace. An unexplained model choice proves
nothing to anyone watching.

**Retrieval is hybrid, not vector-only.** Embeddings reliably fail on exact
identifiers like `P-101B` and clause references. In engineering documents those
are most of the queries, not an edge case. Vector and BM25 results are fused by
reciprocal rank, which needs no score normalisation.

**The index refuses to load if the embedding model changed.** Indexing with one
model and querying with another throws no error and returns quietly meaningless
results. It is the most common failure in this workstream, so it is a hard error
here instead of a mystery later.

**The egress guard intercepts at the socket layer.** Rather than asserting that
nothing leaves the machine, every connection attempt is recorded and anything
that is not loopback raises. `--proof` prints the tally. This is the evidence for
the entire sovereignty claim, and it is deliberately impossible to bypass by
accident.

## Two failure modes the agent loop handles explicitly

Both will happen with local models, and both look like hangs if unhandled.

The model repeating an identical tool call forever, which is caught by signature
counting and answered with a nudge rather than an infinite loop. And the model
emitting prose where JSON was requested, which gets one reprompt before a clean
abort. Tool calling uses our own JSON contract rather than the OpenAI `tools`
parameter, because native tool-call support across MLX, llama.cpp and Ollama is
inconsistent and varies by model. A plain JSON contract works everywhere and you
can read exactly what the model emitted when it goes wrong.

## Reading a trace

`trace.jsonl` records one line per stage: `route`, `retrieve`, `inference`,
`tool_call`, `tool_result`, `sandbox`, `deliverable`, `egress`.

When output is wrong, do not stare at the output. Walk the trace forward and find
the first stage whose intermediate looks wrong. Everything after that point is
downstream noise. Nearly every bug in this system is diagnosed by reading which
chunks came back and what the tool actually returned.

## What is deliberately not done yet

Multimodal ingest has no module — that workstream should add `kb/ingest_scan.py`
exposing `extract(path) -> text` and nothing else, so the agent does not care
whether text came from a PDF layer or from OCR. Always inspect extracted text
before blaming the model; garbage OCR produces a confident, fluent, entirely
fabricated approval note.

The sandbox is a limited subprocess, which is honest for a demo. Say plainly that
production means a container with no network namespace. Do not claim the demo
sandbox is production isolation.

Note what the sandbox can actually enforce per platform. `sandbox.enforced_limits()`
returns the real answer, and it differs: macOS does not honour `RLIMIT_AS`, so on a
Mac the guards are the wall-clock timeout, CPU time and file size, not a memory cap.
Limits are applied best-effort and, if the platform refuses them entirely, the
sandbox drops to timeout-only and marks itself degraded rather than failing the
task. Quote `enforced_limits()` if asked how it is isolated; overclaiming here is
the kind of thing a defence-sector judge will catch.

The approval note template has no letterhead. Add one. It is the artifact judges
will actually look at, and a plain document undersells a working pipeline.
