# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Manage transaction traces: fetch, cache, and display with filtering/decoding."""

import argparse
from collections import OrderedDict
import os
import re
import subprocess
import sys


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

def get_traces(tx_hash, rpc_env_var, labels):
    """Run `cast run` to fetch transaction traces."""
    rpc_url = os.getenv(rpc_env_var)
    if not rpc_url:
        print(f"Error: environment variable {rpc_env_var} is not set.", file=sys.stderr)
        sys.exit(1)
    cmd = ["cast", "run", tx_hash, "--rpc-url", rpc_url]
    if labels:
        for label in labels:
            cmd.extend(["--label", label])
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout


def cache_path(tx_hash):
    """Return the cache file path for a given tx hash."""
    return os.path.join("cached", f"{tx_hash}.txt")


def cmd_get(args):
    """Fetch traces and cache them."""
    path = cache_path(args.tx_hash)
    if os.path.exists(path):
        print(f"Traces already cached at {path}")
        return
    traces = get_traces(args.tx_hash, args.rpc_var, args.label)
    os.makedirs("cached", exist_ok=True)
    with open(path, "w") as f:
        f.write(traces)
    print(f"Cached traces to {path}")


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def compute_depth(line):
    """Compute tree depth by counting tree-drawing characters."""
    return line.count("\u2502") + line.count("\u251c") + line.count("\u2514")


# ---------------------------------------------------------------------------
# Decoding
# ---------------------------------------------------------------------------

def decode_hex_word(word):
    """Heuristically decode a single 32-byte (64 hex char) word."""
    val = int(word, 16)
    if val == 0:
        return "0"
    # Address heuristic: top 12 bytes zero, value large enough to be an address
    if word[:24] == "0" * 24 and val >= 2**64:
        return "0x" + word[24:]
    return str(val)


def decode_hex_data(hex_str):
    """Split hex string into 32-byte words and decode each."""
    if len(hex_str) == 0 or len(hex_str) % 64 != 0:
        return hex_str
    words = [hex_str[i:i + 64] for i in range(0, len(hex_str), 64)]
    decoded = [decode_hex_word(w) for w in words]
    return ", ".join(decoded)


# Raw hex params: ::funcname(PURE_HEX_64+)
_RAW_PARAMS = re.compile(r"(::[\w]+)\(([0-9a-fA-F]{64,})\)")
# Raw hex return: ← [Return] 0xHEX_64+
_RAW_RETURN = re.compile(r"(\u2190 \[Return\]) (0x([0-9a-fA-F]{64,}))$")


def decode_line(line):
    """Decode raw hex data in a trace line. Already-decoded lines are untouched."""
    line = _RAW_PARAMS.sub(
        lambda m: f"{m.group(1)}({decode_hex_data(m.group(2))})", line
    )
    line = _RAW_RETURN.sub(
        lambda m: f"{m.group(1)} {decode_hex_data(m.group(3))}", line
    )
    return line


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------

def filter_by_depth(lines, max_depth):
    """Return lines where tree depth <= max_depth."""
    return [l for l in lines if compute_depth(l) <= max_depth]


def extract_subtree(lines, start_idx):
    """Extract subtree from start_idx until next line at same or lesser depth."""
    root_depth = compute_depth(lines[start_idx])
    subtree = [lines[start_idx]]
    for i in range(start_idx + 1, len(lines)):
        if compute_depth(lines[i]) <= root_depth:
            break
        subtree.append(lines[i])
    return subtree


def filter_by_call(lines, call_name, max_depth=None):
    """Extract subtrees rooted at each call matching call_name."""
    pattern = f"::{call_name}("
    result = []
    covered = set()
    for i, line in enumerate(lines):
        if i in covered:
            continue
        if pattern in line:
            full_subtree = extract_subtree(lines, i)
            for j in range(i, i + len(full_subtree)):
                covered.add(j)
            if max_depth is not None:
                root_depth = compute_depth(lines[i])
                full_subtree = [l for l in full_subtree
                                if compute_depth(l) - root_depth <= max_depth]
            result.extend(full_subtree)
    return result


def filter_by_address(lines, address, max_depth=None):
    """Extract subtrees for lines containing the given address."""
    addr_lower = address.lower()
    result = []
    covered = set()
    for i, line in enumerate(lines):
        if i in covered:
            continue
        if addr_lower in line.lower():
            full_subtree = extract_subtree(lines, i)
            for j in range(i, i + len(full_subtree)):
                covered.add(j)
            if max_depth is not None:
                root_depth = compute_depth(lines[i])
                full_subtree = [l for l in full_subtree
                                if compute_depth(l) - root_depth <= max_depth]
            result.extend(full_subtree)
    return result


def filter_by_contract(lines, contract_name, max_depth=None):
    """Extract subtrees for calls on a given decoded contract name."""
    pattern = f"{contract_name}::"
    pattern_lower = pattern.lower()
    result = []
    covered = set()
    for i, line in enumerate(lines):
        if i in covered:
            continue
        if pattern_lower in line.lower():
            full_subtree = extract_subtree(lines, i)
            for j in range(i, i + len(full_subtree)):
                covered.add(j)
            if max_depth is not None:
                root_depth = compute_depth(lines[i])
                full_subtree = [l for l in full_subtree
                                if compute_depth(l) - root_depth <= max_depth]
            result.extend(full_subtree)
    return result


def filter_by_selector(lines, selector, max_depth=None):
    """Extract subtrees for calls using a given 4-byte hex selector."""
    sel = selector.lower().removeprefix("0x")
    pattern = f"::{sel}("
    result = []
    covered = set()
    for i, line in enumerate(lines):
        if i in covered:
            continue
        if pattern in line.lower():
            full_subtree = extract_subtree(lines, i)
            for j in range(i, i + len(full_subtree)):
                covered.add(j)
            if max_depth is not None:
                root_depth = compute_depth(lines[i])
                full_subtree = [l for l in full_subtree
                                if compute_depth(l) - root_depth <= max_depth]
            result.extend(full_subtree)
    return result


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

# Matches: [gas] ContractOrAddress::function(
_CALL_RE = re.compile(r"\[(\d+)\] (0x[0-9a-fA-F]+|[\w]+)::([\w]+)\(")

# A hex-only function name (unresolved selector)
_HEX_SELECTOR_RE = re.compile(r"^[0-9a-fA-F]+$")


def discover_contracts(lines):
    """Parse trace lines and return an ordered dict of contracts to functions.

    Returns:
        OrderedDict mapping contract identifier to a dict with:
            - "address": hex address or None
            - "name": decoded name or None
            - "functions": list of (func_display, func_type) tuples in call order
              where func_type is "decoded" or "selector"
    """
    contracts = OrderedDict()  # key -> {"address", "name", "functions"}
    seen_funcs = {}  # key -> set of func names already added

    for line in lines:
        m = _CALL_RE.search(line)
        if not m:
            continue

        target = m.group(2)
        func = m.group(3)

        # Determine if target is an address or a decoded name
        if target.startswith("0x"):
            address = target
            name = None
        else:
            address = None
            name = target

        # Use a canonical key for dedup (lowercase address or name)
        key = (address.lower() if address else None, name)

        if key not in contracts:
            contracts[key] = {"address": address, "name": name, "functions": []}
            seen_funcs[key] = set()

        if func not in seen_funcs[key]:
            seen_funcs[key].add(func)
            if _HEX_SELECTOR_RE.match(func):
                func_type = "selector"
            else:
                func_type = "decoded"
            contracts[key]["functions"].append((func, func_type))

    return contracts


def format_discover(contracts):
    """Format discover output as readable text."""
    out = []
    for info in contracts.values():
        # Header: contract identity
        if info["address"] and info["name"]:
            header = f"{info['name']} ({info['address']})"
        elif info["address"]:
            header = info["address"]
        else:
            header = info["name"]
        out.append(header)

        # Functions
        for func, ftype in info["functions"]:
            if ftype == "selector":
                out.append(f"  0x{func}")
            else:
                out.append(f"  {func}")

    return "\n".join(out)


def cmd_discover(args):
    """List all contracts and their functions from a cached trace."""
    path = cache_path(args.tx_hash)
    if not os.path.exists(path):
        print(f"No cached traces for {args.tx_hash}. Run 'get' first.", file=sys.stderr)
        sys.exit(1)
    with open(path) as f:
        raw = f.read()
    lines = raw.split("\n")
    contracts = discover_contracts(lines)
    print(format_discover(contracts))


# ---------------------------------------------------------------------------
# CLI: show
# ---------------------------------------------------------------------------

def cmd_show(args):
    """Display traces with optional filtering and decoding."""
    path = cache_path(args.tx_hash)
    if not os.path.exists(path):
        print(f"No cached traces for {args.tx_hash}. Run 'get' first.", file=sys.stderr)
        sys.exit(1)
    with open(path) as f:
        raw = f.read()

    lines = raw.split("\n")

    # Apply filter (with optional relative depth)
    if args.call:
        lines = filter_by_call(lines, args.call, args.depth)
    elif args.address:
        lines = filter_by_address(lines, args.address, args.depth)
    elif args.contract:
        lines = filter_by_contract(lines, args.contract, args.depth)
    elif args.selector:
        lines = filter_by_selector(lines, args.selector, args.depth)
    elif args.depth is not None:
        lines = filter_by_depth(lines, args.depth)

    # Apply hex decoding unless --raw
    if not args.raw:
        lines = [decode_line(l) for l in lines]

    print("\n".join(lines))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Manage transaction traces")
    sub = parser.add_subparsers(dest="command", required=True)

    # get subcommand
    p_get = sub.add_parser("get", help="Fetch and cache traces")
    p_get.add_argument("--tx-hash", required=True)
    p_get.add_argument("--rpc-var", required=True)
    p_get.add_argument("--label", action="append",
                       help="Label in format <address>:name (repeatable)")

    # show subcommand
    p_show = sub.add_parser("show", help="Display cached traces")
    p_show.add_argument("--tx-hash", required=True)
    p_show.add_argument("--depth", type=int, default=None,
                        help="Max tree depth to display")
    p_show.add_argument("--raw", action="store_true",
                        help="Skip hex decoding, show original trace data")
    p_show.add_argument("--call", default=None,
                        help="Extract subtree of matching function call")
    p_show.add_argument("--address", default=None,
                        help="Show calls involving this address")
    p_show.add_argument("--contract", default=None,
                        help="Show calls on a decoded contract name")
    p_show.add_argument("--selector", default=None,
                        help="Show calls using a 4-byte hex selector")

    # discover subcommand
    p_discover = sub.add_parser("discover",
                                help="List contracts and functions in a trace")
    p_discover.add_argument("--tx-hash", required=True)

    args = parser.parse_args()
    if args.command == "get":
        cmd_get(args)
    elif args.command == "show":
        cmd_show(args)
    elif args.command == "discover":
        cmd_discover(args)


if __name__ == "__main__":
    main()
