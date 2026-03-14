# /// script
# requires-python = ">=3.11"
# dependencies = ["claude-agent-sdk"]
# ///

"""Automated Web3 hack root cause analysis using Claude Agent SDK."""

import argparse
import os
import subprocess
import sys
from pathlib import Path

import anyio
from claude_agent_sdk import query, ClaudeAgentOptions, AgentDefinition, ResultMessage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHAIN_TO_RPC = {
    "eth": "ETH_MAINNET",
    "base": "BASE_MAINNET",
    "op": "OP_MAINNET",
    "arb": "ARB_MAINNET",
}

REPO_ROOT = Path(__file__).parent
TRACES_SCRIPT = REPO_ROOT / "skills" / "manage-tx-traces" / "scripts" / "manage_traces.py"
SOURCE_SCRIPT = REPO_ROOT / "skills" / "get-source-code" / "scripts" / "get_source.py"
TRACES_CWD = REPO_ROOT / "skills" / "manage-tx-traces"
SOURCE_CWD = REPO_ROOT / "skills" / "get-source-code"

TRACE_EXPLORER_PROMPT = """\
You are a trace analysis assistant. Use the manage_traces.py script to explore \
transaction traces. You have access to Bash and Read tools.

The manage_traces.py script is located at: {traces_script}
It must be run with cwd set to: {traces_cwd}

When asked to investigate a specific aspect of a trace, use the appropriate \
filters (--call, --address, --contract, --selector, --depth) and return the \
relevant output. Example:

  uv run {traces_script} show --tx-hash <HASH> --call <FUNCTION> --depth 3
"""

ANALYSIS_SYSTEM_PROMPT = """\
You are an expert Web3 security analyst performing a root cause analysis (RCA) \
of a smart contract hack. Your goal is to identify the vulnerability, its root \
cause, and write a structured RCA report.

## Analysis Guidelines

1. Read the provided trace and source code files thoroughly.
2. Use `manage_traces.py show` with filters (--call, --address, --contract, \
--selector, --depth) via Bash to explore specific subtrees during analysis. \
You can also delegate trace exploration to the `trace-explorer` subagent via \
the Task tool when you want to investigate specific subtrees without spending \
main context.
   - The script is at: {traces_script}
   - It must be run from: {traces_cwd}
   - Example: uv run {traces_script} show --tx-hash {tx_hash} --call transferFrom --depth 3
3. Identify: the vulnerability type, the vulnerable source code snippet, the \
root cause, and the step-by-step attack sequence.
4. Reference specific function calls, addresses, and values from the traces in \
the attack sequence.

## Writing the Report

The report MUST be written using a Python script via Bash that reads traces \
and source code from files. NEVER copy/paste trace or source content into the \
report manually. Use the following approach:

```python
python3 << 'PYEOF'
with open('<traces_file>', 'r') as f:
    traces = f.read()
with open('<source_file>', 'r') as f:
    source_code = f.read()

report = f\"\"\"### Tx Hash
<TX_HASH>
### Chain
<CHAIN>
### Tx Trace
```
{{traces}}
```
### Source Code
```solidity
{{source_code}}
```
### Vulnerability Type
<VULNERABILITY_TYPE>
### Vulnerable Source Code
```solidity
<VULNERABLE_CODE_SNIPPET>
```
### Root Cause
<ROOT_CAUSE_EXPLANATION>
### Attack Sequence
<NUMBERED_ATTACK_STEPS>
\"\"\"

with open('<output_file>', 'w') as f:
    f.write(report)
print("Report written successfully!")
PYEOF
```

Key rules:
- Never copy/paste trace or source code content manually into the report
- Always use file reads to insert trace and source code content via f-string
- The vulnerable source code snippet is an extracted subset of the source code \
that you identify as vulnerable — do not annotate it
- If traces are too long, re-run manage_traces.py show with --depth N to trim them

## Report Template

The report must follow this structure:
- Tx Hash
- Chain
- Tx Trace (inserted from file)
- Source Code (inserted from file)
- Vulnerability Type
- Vulnerable Source Code (snippet you identify)
- Root Cause
- Attack Sequence (numbered steps referencing trace data)
"""


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_env(chain: str) -> str:
    """Validate required environment variables. Returns the RPC env var name."""
    rpc_var = CHAIN_TO_RPC.get(chain)
    if rpc_var is None:
        print(f"Error: unsupported chain '{chain}'. Supported: {', '.join(CHAIN_TO_RPC)}", file=sys.stderr)
        sys.exit(1)

    missing = []
    if not os.getenv(rpc_var):
        missing.append(rpc_var)
    if not os.getenv("ETHERSCAN_API_KEY"):
        missing.append("ETHERSCAN_API_KEY")
    if not os.getenv("ANTHROPIC_API_KEY"):
        missing.append("ANTHROPIC_API_KEY")

    if missing:
        print(f"Error: missing environment variable(s): {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    return rpc_var


# ---------------------------------------------------------------------------
# Data Gathering
# ---------------------------------------------------------------------------

def run_cmd(cmd: list[str], cwd: Path, capture: bool = False, stdout_file: str | None = None) -> str:
    """Run a subprocess command, optionally capturing or redirecting output."""
    print(f"  → {' '.join(str(c) for c in cmd[:5])}{'...' if len(cmd) > 5 else ''}")
    if stdout_file:
        with open(stdout_file, "w") as f:
            result = subprocess.run(cmd, cwd=cwd, stdout=f, stderr=subprocess.PIPE, text=True)
    elif capture:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    else:
        result = subprocess.run(cmd, cwd=cwd, stderr=subprocess.PIPE, text=True)

    if result.returncode != 0:
        print(f"Error running command: {' '.join(str(c) for c in cmd)}", file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        sys.exit(1)

    return result.stdout if capture else ""


def gather_data(tx_hash: str, contracts: list[str], chain: str, rpc_var: str) -> tuple[str, str, str]:
    """Fetch traces and source code. Returns (traces_file, source_file, discover_output)."""
    traces_file = f"/tmp/rca_traces_{tx_hash[:10]}.txt"
    source_file = f"/tmp/rca_source_{tx_hash[:10]}.txt"

    # Step 1: Fetch and cache traces
    print("\n[1/4] Fetching and caching traces...")
    run_cmd(
        ["uv", "run", str(TRACES_SCRIPT), "get", "--tx-hash", tx_hash, "--rpc-var", rpc_var],
        cwd=TRACES_CWD,
    )

    # Step 2: Save full traces to file
    print("[2/4] Saving traces to file...")
    run_cmd(
        ["uv", "run", str(TRACES_SCRIPT), "show", "--tx-hash", tx_hash],
        cwd=TRACES_CWD,
        stdout_file=traces_file,
    )

    # Step 3: Discover contracts/functions
    print("[3/4] Discovering contracts and functions...")
    discover_output = run_cmd(
        ["uv", "run", str(TRACES_SCRIPT), "discover", "--tx-hash", tx_hash],
        cwd=TRACES_CWD,
        capture=True,
    )

    # Step 4: Save source code to file
    print("[4/4] Retrieving source code...")
    run_cmd(
        ["uv", "run", str(SOURCE_SCRIPT), ",".join(contracts), chain, "--traces", traces_file],
        cwd=SOURCE_CWD,
        stdout_file=source_file,
    )

    return traces_file, source_file, discover_output


# ---------------------------------------------------------------------------
# Agent Analysis
# ---------------------------------------------------------------------------

async def run_analysis(
    tx_hash: str,
    chain: str,
    traces_file: str,
    source_file: str,
    discover_output: str,
    output_file: str,
    model: str,
) -> None:
    """Launch Claude agent to analyze the hack and write the report."""
    system_prompt = ANALYSIS_SYSTEM_PROMPT.format(
        traces_script=TRACES_SCRIPT,
        traces_cwd=TRACES_CWD,
        tx_hash=tx_hash,
    )

    trace_explorer_prompt = TRACE_EXPLORER_PROMPT.format(
        traces_script=TRACES_SCRIPT,
        traces_cwd=TRACES_CWD,
    )

    user_prompt = f"""\
Analyze the following Web3 hack and write an RCA report.

Tx Hash: {tx_hash}
Chain: {chain}

Contracts and functions discovered in the trace:
{discover_output}

Trace file path: {traces_file}
Source code file path: {source_file}
Output report path: {output_file}

Read the trace and source code files, analyze the hack, then write the report \
to the output path using a Python script that reads files directly (never copy/paste \
trace or source content)."""

    print(f"\nLaunching Claude agent (model: {model})...\n")

    async for message in query(
        prompt=user_prompt,
        options=ClaudeAgentOptions(
            cwd=str(REPO_ROOT),
            allowed_tools=["Read", "Write", "Bash", "Glob", "Grep", "Task"],
            permission_mode="dontAsk",
            model=model,
            system_prompt=system_prompt,
            max_turns=30,
            thinking={"type": "adaptive"},
            agents={
                "trace-explorer": AgentDefinition(
                    description="Explore and filter transaction traces using manage_traces.py show with various filters (--call, --address, --contract, --selector, --depth). Use this to investigate specific subtrees without consuming main agent context.",
                    prompt=trace_explorer_prompt,
                    tools=["Bash", "Read"],
                )
            },
        ),
    ):
        if isinstance(message, ResultMessage):
            print(message.result)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Automated Web3 hack root cause analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Example:
  uv run run_rca.py --tx-hash 0x889... --contracts 0x6f95... --chain eth
""",
    )
    parser.add_argument("--tx-hash", required=True, help="Transaction hash of the hack")
    parser.add_argument("--contracts", required=True, help="Comma-separated contract addresses for source code retrieval")
    parser.add_argument("--chain", required=True, choices=CHAIN_TO_RPC.keys(), help="Chain identifier")
    parser.add_argument("--output", default=None, help="Output file path (default: rca-<tx_hash_first_10>.md)")
    parser.add_argument("--model", default="claude-opus-4-6", help="Claude model to use (default: claude-opus-4-6)")
    args = parser.parse_args()

    tx_hash = args.tx_hash
    contracts = [addr.strip() for addr in args.contracts.split(",") if addr.strip()]
    chain = args.chain
    output_file = args.output or f"rca-{tx_hash[:10]}.md"
    model = args.model

    # Validate
    print("Validating environment...")
    rpc_var = validate_env(chain)

    # Gather data
    print("Gathering data...")
    traces_file, source_file, discover_output = gather_data(tx_hash, contracts, chain, rpc_var)
    print(f"\nTraces saved to: {traces_file}")
    print(f"Source saved to: {source_file}")

    # Run analysis
    anyio.run(run_analysis, tx_hash, chain, traces_file, source_file, discover_output, output_file, model)

    # Check output
    if os.path.exists(output_file):
        print(f"\nRCA report written to: {output_file}")
    else:
        print(f"\nWarning: expected output file {output_file} was not created.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
