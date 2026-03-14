---
name: make-hack-rca
description: Procedure and formatting guidelines for creating Web3 root cause analyses
---

# Make hack root cause analysis (RCA)

This skill outlines the procedure and formatting guidelines for creating Web3 hack root cause analyses (RCAs). Web3 hacks can be very complex, and as such breaking down their components and locating the root cause within a smart contract is comprised of several steps:

1. **User-provided details:** The user is expected to provide the transaction (tx) hash of a suspected hack, the contract address(es) to retrieve source code of, and the chain where the hack occurred.
2. **Retrieving tx traces:** The next step is to retrieve the tx traces of the hack, which contain details about setup, what functions were called with specific parameters, and the impact of those calls (funds stolen, invariants broken, etc.). To get tx traces, a separate skill should be used called `manage-tx-traces`. The tx traces should be stored in a temporary file for source code retrieval in the next step.
3. **Source code retrieval:** Next the source code of the provided contract address(es) should be retrieved. The source code is key to identifying the root cause of the hack. To get source code, a separate skill should be used called `get-source-code`. This skill makes use of a script that has an optional parameter for using the tx traces to get only the most relevant source code. Since the tx traces were retrieved and stored in a separate step, the optional parameter should always be provided.
4. **Tx trace and source code analysis:** With the tx traces and source code retrieved, the root cause and vulnerable source code can then be identified. The setup and post-exploit funds movement should be ignored in favor of locating the specific function calls with values and corresponding source code that leads to the vulnerable source code of the hack.
5. **Writing the analysis report:** Once the root cause is found, the tx hash, chain, tx traces, source code, generalized vulnerability type, vulnerable source code snippet, root cause, and attack sequence should be written up into a markdown file.

## Formatting

The template that should be used can be found under the sub-directory `templates/` within this skill. Note that any brevity and annotation that may be found in the examples is only for showcasing how the examples look specifically. DO NOT truncate, annotate, or otherwise modify the tx traces, source code, and vulnerable source code sections. To trim tx traces, use the `manage-tx-traces` skill with `--depth N` to limit trace depth, or `--call`/`--address` to extract specific subtrees.

When writing the attack sequence, it is important to reference as much as possible the function calls, addresses, and other relevant data within the tx trace itself. Generalizing the attack sequence is discouraged when information from the trace can be extracted instead.

## Writing the Report

To ensure tx traces, source code, and vulnerable source code snippets are not modified, truncated, or annotated, the report must be written using a script that reads the outputs directly from files. The following pseudocode outlines the required process:

```pseudocode
# Step 1: Fetch and cache tx traces (use manage-tx-traces skill)
run: manage_traces.py get --tx-hash <TX_HASH> --rpc-var <RPC_VAR>

# Step 2: Save tx traces to a temp file (use --depth N if needed to trim)
run: manage_traces.py show --tx-hash <TX_HASH> [--depth N] > /tmp/traces.txt

# Step 3: Save source code to a temp file (use get-source-code skill with --traces)
run: get_source.py <CONTRACT_ADDRESS> <CHAIN> --traces <TRACES_FILE> > /tmp/source.txt

# Step 4: Write the report using Python to read files directly (NO manual copying)
run: python3 << 'EOF'
# Read traces from file
with open('/tmp/traces.txt', 'r') as f:
    traces = f.read()

# Read source code from file
with open('/tmp/source.txt', 'r') as f:
    source_code = f.read()

# Construct the report - traces and source_code are inserted AS-IS
report = f"""
### Tx Hash
<TX_HASH>
### Chain
<CHAIN>
### Tx Trace
```
{traces}
```
### Source Code
```solidity
{source_code}
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
"""

# Write the report
with open('<PROTOCOL_NAME>-<YEAR>.md', 'w') as f:
    f.write(report)

print("Report written successfully!")
EOF
```

**Key Rules:**
1. Never copy/paste trace or source code content manually into the report
2. Always use file reads to insert trace and source code content
3. Only the following sections may be written manually:
   - Tx Hash
   - Chain
   - Vulnerability Type
   - Vulnerable Source Code snippet (extracted subset of source code - do not annotate)
   - Root Cause
   - Attack Sequence
4. If traces are too long, re-run manage_traces.py show with `--depth N` (lower N = less detail)
5. The `{traces}` and `{source_code}` variables must be inserted using f-string interpolation

## Examples

Examples of Web3 hack root cause analyses (RCAs) can be found under the sub-directory `examples/` within this skill.
