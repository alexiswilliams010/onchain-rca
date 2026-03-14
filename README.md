# Onchain Root Cause Analysis

A collection of Claude code skills for performing root cause analyses (RCAs) of smart contract hacks. Each skill encapsulates a specific step in the investigation pipeline, from fetching onchain transaction traces to retrieving verified source code and writing a structured analysis report.

## Overview

Investigating a Web3 hack is a multi-step process that requires pulling data from several sources and synthesizing it into a coherent explanation of what went wrong and why. This plugin provides a set of composable skills that guide an agent through that entire workflow in a repeatable, structured way.

The output of the full pipeline is a markdown RCA report covering:

- The exploit transaction hash and chain
- Full transaction traces
- Relevant smart contract source code
- Vulnerability type classification
- The vulnerable source code snippet
- A plain-language root cause explanation
- A step-by-step attack sequence grounded in onchain data

## Prerequisites

| Tool / Variable | Purpose |
|---|---|
| [`uv`](https://docs.astral.sh/uv/getting-started/installation/) | Runs Python scripts and manages dependencies |
| [`cast`](https://book.getfoundry.sh/getting-started/installation) | Replays transactions to generate traces |
| `ETHERSCAN_API_KEY` | Authenticates source code lookups via Etherscan |

## Automated RCA Script

`run_rca.py` automates the entire RCA pipeline as a single CLI invocation. It gathers traces and source code via subprocess, then launches a Claude agent to analyze the exploit and write the report — no interactive session required.

### Additional Prerequisites

| Tool / Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Authenticates with the Claude API for agent analysis |
| [Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code) | Required by `claude-agent-sdk` |

### Usage

```bash
cd /path/to/onchain-rca
uv run run_rca.py --tx-hash <HASH> --contracts <ADDR1,ADDR2,...> --chain <CHAIN> \
    [--output FILE] [--model MODEL]
```

| Argument | Required | Description |
|----------|----------|-------------|
| `--tx-hash` | Yes | Transaction hash of the hack |
| `--contracts` | Yes | Comma-separated contract addresses for source code retrieval |
| `--chain` | Yes | Chain identifier (`eth`, `base`, `op`, `arb`) |
| `--output` | No | Output file path (default: `rca-<tx_hash_first_10>.md`) |
| `--model` | No | Claude model to use (default: `claude-opus-4-6`) |

### Example

```bash
uv run run_rca.py \
    --tx-hash 0x889e80e5596af34a544d4b517bf559434e3b7e57a79e2981e4b03e7abb94ae82 \
    --contracts 0x6f95d4d251053483f41c8718C30F4F3C404A8cf2 \
    --chain eth
```

## Skills

### `make-hack-rca`

**Procedure and formatting guidelines for creating Web3 root cause analyses.**

Orchestrates the full RCA workflow. Given a transaction hash, contract address(es), and chain, it coordinates the other skills to retrieve traces and source code, analyzes the exploit, and writes a structured markdown report. The report is generated via a script that reads trace and source code files directly, ensuring those sections are never truncated, annotated, or manually copied.

### `manage-tx-traces`

**Fetch, cache, and display transaction traces for a given tx hash.**

Uses `cast run` (Foundry) under the hood to replay a transaction against historical chain state and extract its full call trace. Traces are cached locally for reuse. The `show` subcommand provides hex decoding of raw ABI data and filtering by depth, function call, address, contract name, or selector. The `discover` subcommand lists all contracts and functions found in a trace.

### `get-source-code`

**Retrieve verified source code for one or more smart contract addresses.**

Fetches verified source code from Etherscan for a given contract address and chain. When a traces file is provided via the optional `--traces` argument, the script narrows the output to only the source code most relevant to the exploit, reducing noise for analysis.

### Supported Chains

The following chains are supported. Each requires the corresponding RPC URL to be set as an environment variable for trace retrieval.

| Chain | `chain` value | RPC env var |
|---|---|---|
| Ethereum | `eth` | `ETH_MAINNET` |
| Base | `base` | `BASE_MAINNET` |
| Optimism | `op` | `OP_MAINNET` |
| Arbitrum | `arb` | `ARB_MAINNET` |
