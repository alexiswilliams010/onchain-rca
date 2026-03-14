# /// script
# requires-python = ">=3.11"
# dependencies = ["claude-agent-sdk"]
# ///

"""Automated Web3 hack root cause analysis using Claude Agent SDK."""

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path

import anyio
from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    AgentDefinition,
    AssistantMessage,
    ResultMessage,
    SystemMessage,
)


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

class _ColorFormatter(logging.Formatter):
    """Colored log formatter with category-aware styling."""

    RESET = "\033[0m"
    COLORS = {
        "DEBUG":    "\033[90m",        # gray
        "INFO":     "\033[36m",        # cyan
        "WARNING":  "\033[33m",        # yellow
        "ERROR":    "\033[31m",        # red
        "CRITICAL": "\033[1;31m",      # bold red
    }
    # Extra colors for structured categories
    CATEGORY = {
        "phase":    "\033[1;34m",      # bold blue
        "step":     "\033[34m",        # blue
        "cmd":      "\033[90m",        # gray
        "tool":     "\033[35m",        # magenta
        "agent":    "\033[1;35m",      # bold magenta
        "session":  "\033[36m",        # cyan
        "result":   "\033[1;32m",      # bold green
        "cost":     "\033[33m",        # yellow
    }

    def __init__(self, use_color: bool = True):
        super().__init__()
        self._use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        cat = getattr(record, "cat", None)
        msg = record.getMessage()

        if not self._use_color:
            if cat:
                return f"  [{cat}] {msg}"
            return msg

        if cat and cat in self.CATEGORY:
            color = self.CATEGORY[cat]
            label = f"{color}[{cat}]{self.RESET}"
            return f"  {label} {msg}"

        color = self.COLORS.get(record.levelname, "")
        return f"{color}{msg}{self.RESET}"


log = logging.getLogger("rca")


def _setup_logging(verbose: bool) -> None:
    """Configure the rca logger with colored output."""
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_ColorFormatter(use_color=sys.stderr.isatty()))
    log.addHandler(handler)
    log.setLevel(logging.DEBUG if verbose else logging.INFO)

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
        log.error("Unsupported chain '%s'. Supported: %s", chain, ", ".join(CHAIN_TO_RPC))
        sys.exit(1)

    missing = []
    if not os.getenv(rpc_var):
        missing.append(rpc_var)
    if not os.getenv("ETHERSCAN_API_KEY"):
        missing.append("ETHERSCAN_API_KEY")
    if not os.getenv("ANTHROPIC_API_KEY"):
        missing.append("ANTHROPIC_API_KEY")

    if missing:
        log.error("Missing environment variable(s): %s", ", ".join(missing))
        sys.exit(1)

    return rpc_var


# ---------------------------------------------------------------------------
# Data Gathering
# ---------------------------------------------------------------------------

def run_cmd(cmd: list[str], cwd: Path, capture: bool = False, stdout_file: str | None = None) -> str:
    """Run a subprocess command, optionally capturing or redirecting output."""
    preview = " ".join(str(c) for c in cmd[:5]) + ("..." if len(cmd) > 5 else "")
    log.debug(preview, extra={"cat": "cmd"})

    if stdout_file:
        with open(stdout_file, "w") as f:
            result = subprocess.run(cmd, cwd=cwd, stdout=f, stderr=subprocess.PIPE, text=True)
    elif capture:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    else:
        result = subprocess.run(cmd, cwd=cwd, stderr=subprocess.PIPE, text=True)

    if result.returncode != 0:
        log.error("Command failed: %s", " ".join(str(c) for c in cmd))
        if result.stderr:
            log.error(result.stderr.strip())
        sys.exit(1)

    return result.stdout if capture else ""


def gather_data(tx_hash: str, contracts: list[str], chain: str, rpc_var: str) -> tuple[str, str, str]:
    """Fetch traces and source code. Returns (traces_file, source_file, discover_output)."""
    traces_file = f"/tmp/rca_traces_{tx_hash[:10]}.txt"
    source_file = f"/tmp/rca_source_{tx_hash[:10]}.txt"

    log.info("Fetching and caching traces", extra={"cat": "step"})
    run_cmd(
        ["uv", "run", str(TRACES_SCRIPT), "get", "--tx-hash", tx_hash, "--rpc-var", rpc_var],
        cwd=TRACES_CWD,
    )

    log.info("Saving traces to file", extra={"cat": "step"})
    run_cmd(
        ["uv", "run", str(TRACES_SCRIPT), "show", "--tx-hash", tx_hash],
        cwd=TRACES_CWD,
        stdout_file=traces_file,
    )

    log.info("Discovering contracts and functions", extra={"cat": "step"})
    discover_output = run_cmd(
        ["uv", "run", str(TRACES_SCRIPT), "discover", "--tx-hash", tx_hash],
        cwd=TRACES_CWD,
        capture=True,
    )

    log.info("Retrieving source code", extra={"cat": "step"})
    run_cmd(
        ["uv", "run", str(SOURCE_SCRIPT), ",".join(contracts), chain, "--traces", traces_file],
        cwd=SOURCE_CWD,
        stdout_file=source_file,
    )

    return traces_file, source_file, discover_output


# ---------------------------------------------------------------------------
# Agent Analysis
# ---------------------------------------------------------------------------

_TOOL_FORMATTERS: dict[str, callable] = {
    "Bash":  lambda inp: inp.get("command", "")[:120],
    "Read":  lambda inp: inp.get("file_path", "?"),
    "Write": lambda inp: inp.get("file_path", "?"),
    "Edit":  lambda inp: inp.get("file_path", "?"),
    "Glob":  lambda inp: inp.get("pattern", "?"),
    "Grep":  lambda inp: inp.get("pattern", "?"),
    "Task":  lambda inp: (inp.get("description") or inp.get("prompt", "?"))[:100],
}


def _log_assistant(message: AssistantMessage) -> None:
    """Log assistant message: stream text to stdout, tool calls to debug log."""
    for block in message.content:
        if hasattr(block, "text") and block.text:
            sys.stdout.write(block.text)
            sys.stdout.flush()
        elif hasattr(block, "type") and block.type == "tool_use":
            name = getattr(block, "name", "?")
            tool_input = getattr(block, "input", {})
            fmt = _TOOL_FORMATTERS.get(name, lambda _: "")
            detail = fmt(tool_input)
            if detail:
                log.debug("%s %s", name, detail, extra={"cat": "tool"})
            else:
                log.debug("%s", name, extra={"cat": "tool"})


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

    log.info("Launching agent (model: %s)", model, extra={"cat": "agent"})

    turn_count = 0

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
        if isinstance(message, SystemMessage):
            subtype = getattr(message, "subtype", "")
            if subtype == "init":
                session_id = getattr(message, "session_id", None) or (
                    message.data.get("session_id") if hasattr(message, "data") else None
                )
                log.debug("Session %s", session_id, extra={"cat": "session"})
            elif subtype == "compact_boundary":
                log.debug("Context window compacted", extra={"cat": "session"})

        elif isinstance(message, AssistantMessage):
            turn_count += 1
            log.debug("Turn %d", turn_count, extra={"cat": "agent"})
            _log_assistant(message)

        elif isinstance(message, ResultMessage):
            # Ensure a newline after any streamed text
            sys.stdout.write("\n")
            sys.stdout.flush()

            if message.subtype == "success":
                cost = message.total_cost_usd
                turns = message.num_turns
                cost_str = f"${cost:.4f}" if cost is not None else "N/A"
                log.info("Completed in %s turns, cost: %s", turns, cost_str, extra={"cat": "result"})
            else:
                log.error("Agent stopped: %s", message.subtype)
                if message.subtype == "error_max_turns":
                    log.warning("Hint: increase --max-turns or simplify the task")
                if message.total_cost_usd is not None:
                    log.info("Cost: $%s", f"{message.total_cost_usd:.4f}", extra={"cat": "cost"})


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
    parser.add_argument("-v", "--verbose", action="store_true", help="Show agent tool calls and session details")
    args = parser.parse_args()

    tx_hash = args.tx_hash
    contracts = [addr.strip() for addr in args.contracts.split(",") if addr.strip()]
    chain = args.chain
    output_file = args.output or f"rca-{tx_hash[:10]}.md"
    model = args.model

    _setup_logging(args.verbose)

    # Validate
    log.info("Validating environment", extra={"cat": "phase"})
    rpc_var = validate_env(chain)

    # Gather data
    log.info("Gathering data", extra={"cat": "phase"})
    traces_file, source_file, discover_output = gather_data(tx_hash, contracts, chain, rpc_var)
    log.debug("Traces: %s", traces_file, extra={"cat": "step"})
    log.debug("Source: %s", source_file, extra={"cat": "step"})

    # Run analysis
    log.info("Analyzing exploit", extra={"cat": "phase"})
    anyio.run(run_analysis, tx_hash, chain, traces_file, source_file, discover_output, output_file, model)

    # Check output
    if os.path.exists(output_file):
        log.info("Report written to %s", output_file, extra={"cat": "result"})
    else:
        log.error("Expected output file %s was not created", output_file)
        sys.exit(1)


if __name__ == "__main__":
    main()
