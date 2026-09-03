"""Runs without any model server. Proves the plumbing works before models exist.

This is the thin end-to-end path. Get this green on day one, then replace
the stubs one at a time.
"""
import sys
sys.path.insert(0, "..")
from core import guard, trace
from agent import tools
from agent.tools_impl import docgen, sandbox

guard.install()

print("1. sandbox executes code")
r = sandbox.run_python("print(sum(range(10)))")
assert r["ok"] and "45" in r["stdout"], r
print("   ok:", r["stdout"].strip())

print("2. sandbox contains a crash")
r = sandbox.run_python("raise ValueError('boom')")
assert not r["ok"] and "boom" in r["stderr"]
print("   ok: crash captured, host unaffected")

print("3. deliverable generation")
p = docgen.approval_note(
    title="Inspection Approval Note",
    reference="VS/INSP/2026/014",
    background="Routine inspection of pump P-101B carried out on site.",
    findings=[
        {"item": "Casing", "observation": "Hairline crack at flange", "severity": "High"},
        {"item": "Bearing", "observation": "Within tolerance", "severity": "Nil"},
    ],
    recommendation="Replace casing before returning the unit to service.",
    prepared_by="Inspection Cell",
)
print("   ok:", p)

print("4. egress guard blocks external calls")
import socket
try:
    socket.socket().connect(("8.8.8.8", 53))
    print("   FAIL: guard did not block")
except PermissionError as e:
    print("   ok:", e)

print("\negress summary:", guard.summary())
print("\ntrace stages:", [e["stage"] for e in trace.read_all()])
