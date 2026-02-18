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

## Skills

### `make-hack-rca`

**Procedure and formatting guidelines for creating Web3 root cause analyses.**

Orchestrates the full RCA workflow. Given a transaction hash, contract address(es), and chain, it coordinates the other skills to retrieve traces and source code, analyzes the exploit, and writes a structured markdown report. The report is generated via a script that reads trace and source code files directly, ensuring those sections are never truncated, annotated, or manually copied.

### `get-tx-traces`

**Retrieve transaction traces for a given tx hash.**

Uses `cast run` (Foundry) under the hood to replay a transaction against historical chain state and extract its full call trace. Supports multiple chains via RPC environment variables, address labeling, and a verbosity flag to control trace depth.

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
