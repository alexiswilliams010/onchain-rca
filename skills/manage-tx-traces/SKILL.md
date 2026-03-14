---
name: manage-tx-traces
description: Fetch, cache, and display transaction (tx) traces of contract interactions
---

# Manage tx traces

## Prerequisites

- `uv` must be installed. It is used to run the script and automatically manage its dependencies. Installation instructions: https://docs.astral.sh/uv/getting-started/installation/
- `cast` (part of Foundry) must be installed. The script uses `cast run` under the hood to replay transactions and retrieve traces. Installation instructions: https://book.getfoundry.sh/getting-started/installation
- The relevant RPC URL environment variable must be set for the chain you want to query. See the `--rpc-var` section below for the expected variable names.

This skill provides three subcommands for managing transaction traces:

- **`get`** — Fetch traces via `cast run` and cache them locally
- **`show`** — Display cached traces with optional filtering and hex decoding
- **`discover`** — List all contracts and their functions found in a trace

## Usage

### Fetch and cache traces

```bash
uv run scripts/manage_traces.py get --tx-hash <HASH> --rpc-var <RPC_VAR> [--label <address>:<name>]
```

The `get` subcommand runs `cast run` to replay the transaction and caches the raw trace output to `cached/<tx_hash>.txt`. If traces are already cached, it skips the fetch.

Note that the invocation can take a few minutes to run, as transactions have to be processed from their point within the historical block. All prior transactions in the block must also be processed to ensure correct chain state. It is possible for the invocation to fail with a 429 error if a block contains many transactions; retrying should work.

### Discover contracts and functions

```bash
uv run scripts/manage_traces.py discover --tx-hash <HASH>
```

The `discover` subcommand parses a cached trace and lists every contract involved along with the functions called on it. Contracts are shown by address or decoded name (as resolved by `cast`). Functions are listed in call order, with unresolved hex selectors prefixed with `0x`.

### Display traces

```bash
uv run scripts/manage_traces.py show --tx-hash <HASH> [--depth N] [--raw] [--call <name>] [--address <addr>] [--contract <name>] [--selector <hex>]
```

The `show` subcommand displays cached traces with automatic hex decoding and optional filtering.

## Parameters

### `--rpc-var` (get only)

The following environment variable names are supported:

```
ETH_MAINNET -- ethereum (eth) network
BASE_MAINNET -- base network
OP_MAINNET -- optimism (op) network
ARB_MAINNET -- arbitrum (arb) network
```

### `--label` (get only)

Format: `<address>:name`. Can be used multiple times. Labels are passed to `cast run` to label addresses in the trace. Only use labels explicitly provided by the user.

### `--depth N` (show only)

Limit trace output to lines at tree depth ≤ N. When combined with `--call` or `--address`, depth is **relative** to the matched call (e.g., `--depth 1` shows the matched call and its direct children only).

### `--raw` (show only)

Skip hex decoding and show the original trace data. Filters still apply.

### `--call <name>` (show only)

Extract the subtree rooted at each call matching the given function name or selector. All occurrences are shown. Cannot be combined with `--address`.

### `--address <addr>` (show only)

Show all calls where the given address appears, with their full subtrees. Case-insensitive matching.

### `--contract <name>` (show only)

Show all calls on a decoded contract name (e.g., `Unitroller`, `Oracle`). Matches `ContractName::` in trace lines. Case-insensitive matching. When combined with `--depth`, depth is **relative** to each matched call.

### `--selector <hex>` (show only)

Show all calls using a raw 4-byte hex function selector (e.g., `3027fe66`). Accepts with or without `0x` prefix. Case-insensitive matching. When combined with `--depth`, depth is **relative** to each matched call.

Only one of `--call`, `--address`, `--contract`, or `--selector` can be used at a time.

## Hex Decoding

By default, `show` decodes raw hex data in trace output:

- **Raw hex parameters** (e.g., `::func(0000...2d0ca45d09c36880...)`) are split into 32-byte words and decoded as address, uint256, or zero
- **Raw hex return values** (e.g., `← [Return] 0x000000...`) are decoded the same way
- Already-decoded lines (e.g., `borrow(60384500431 [6.038e10])`) are left untouched

Use `--raw` to disable decoding.

IMPORTANT: Do not truncate or otherwise modify traces returned by the script. Use the `--depth` flag to limit the depth of traces returned, or `--call`/`--address`/`--contract`/`--selector` to extract specific subtrees. It is important that the traces remain unmodified (except by using these flags).

## Examples

```bash
# Fetch traces for a transaction
uv run scripts/manage_traces.py get --tx-hash 0xd813... --rpc-var ETH_MAINNET

# Show full decoded trace
uv run scripts/manage_traces.py show --tx-hash 0xd813...

# Show top-level calls only
uv run scripts/manage_traces.py show --tx-hash 0xd813... --depth 1

# Show raw trace without decoding
uv run scripts/manage_traces.py show --tx-hash 0xd813... --raw

# Extract subtree of a specific function call
uv run scripts/manage_traces.py show --tx-hash 0xd813... --call borrow

# Extract borrow subtree, clipped to 2 levels deep
uv run scripts/manage_traces.py show --tx-hash 0xd813... --call borrow --depth 2

# Show all calls involving a specific address
uv run scripts/manage_traces.py show --tx-hash 0xd813... --address 0x912f8C412fF54a8773eE54a826142876077e9501

# Same but only show direct children of each matched call
uv run scripts/manage_traces.py show --tx-hash 0xd813... --address 0x912f8C412fF54a8773eE54a826142876077e9501 --depth 1

# Show all calls on a specific contract
uv run scripts/manage_traces.py show --tx-hash 0xd813... --contract Unitroller

# Show all calls using a specific hex selector
uv run scripts/manage_traces.py show --tx-hash 0xd813... --selector 3027fe66

# Discover all contracts and functions in a trace
uv run scripts/manage_traces.py discover --tx-hash 0xd813...
```
