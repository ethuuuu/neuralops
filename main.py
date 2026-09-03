"""Entry point. The egress guard is installed before anything else."""
import sys, json
from core import guard, registry, trace

guard.install(registry.get("egress", {}).get("allowed_hosts"))

from agent import loop  # noqa: E402  imported after the guard is armed


def main():
    if len(sys.argv) < 2:
        print("usage: python main.py \"<your request>\"")
        print("       python main.py --proof")
        return
    if sys.argv[1] == "--proof":
        print(json.dumps(guard.summary(), indent=2))
        return

    result = loop.run(" ".join(sys.argv[1:]))
    print("\n" + "=" * 60)
    print(result.get("answer") or result.get("error"))
    print("=" * 60)
    print(f"model: {result.get('model')}  |  reason: {result.get('route_reason')}"
          f"  |  steps: {result.get('steps')}")
    print("egress:", json.dumps(guard.summary()))


if __name__ == "__main__":
    main()
