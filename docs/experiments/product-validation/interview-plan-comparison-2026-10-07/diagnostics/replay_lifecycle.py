"""One-variable lifecycle controls for the unchanged finite baseline replay."""

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

import replay
from openai import AsyncStream


async def explicit_outer_iterator(client, request):
    stream = await client.responses.create(**request.create_payload())
    if not isinstance(stream, AsyncStream):
        raise TypeError("Recorded control expects the original SDK stream")
    terminal = None
    iterator = stream.__aiter__()
    try:
        async for event in iterator:
            if event.type in {"response.completed", "response.failed", "response.incomplete"}:
                terminal = event.response
                break
    finally:
        try:
            await iterator.aclose()
        finally:
            await stream.close()
    if terminal is None:
        raise RuntimeError("Control received no terminal envelope")
    return terminal


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("variant", choices=["no-observed", "outer-iterator", "owned-observed"])
    parser.add_argument("tag")
    parser.add_argument("--seconds", type=int, default=120)
    args = parser.parse_args()
    if re.fullmatch(r"[a-z0-9-]{1,80}", args.tag) is None:
        raise ValueError("Invalid diagnostic artifact tag")
    if args.variant == "no-observed":
        replay.ObservedStream = lambda original, observer: original
    elif args.variant == "owned-observed":
        from append_stream import OwnedObservedStream

        replay.ObservedStream = OwnedObservedStream
    else:
        replay.create_response = explicit_outer_iterator
    sys.argv = [str(Path(replay.__file__)), "combined", "--seconds", str(args.seconds)]
    asyncio.run(replay.main(), loop_factory=asyncio.SelectorEventLoop)
    source = replay.HERE / "combined-result.json"
    result = json.loads(source.read_text(encoding="utf-8"))
    result["diagnostic_variant"] = args.variant
    target = replay.HERE / (args.tag + "-result.json")
    if target.exists():
        raise RuntimeError("Diagnostic artifact already exists")
    target.write_text(json.dumps(result, indent=2), encoding="utf-8")
    source.unlink()


if __name__ == "__main__":
    main()
