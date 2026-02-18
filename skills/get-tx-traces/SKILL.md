---
name: get-tx-traces
description: Get transaction (tx) traces of contract interactions via a provided tx hash
---

# Get tx traces

## Prerequisites

- `uv` must be installed. It is used to run the script and automatically manage its dependencies. Installation instructions: https://docs.astral.sh/uv/getting-started/installation/
- `cast` (part of Foundry) must be installed. The script uses `cast run` under the hood to replay transactions and retrieve traces. Installation instructions: https://book.getfoundry.sh/getting-started/installation
- The relevant RPC URL environment variable must be set for the chain you want to query. See the `--rpc-var` section below for the expected variable names.

This skill enables the retrieval of transaction (tx) traces of contract interactions via a provided tx-hash. The user is expected to provide the tx hash as well as the chain that corresponds to an available RPC URL to use for trace retieval. To retrieve the tx trace, the script `get_traces.py` is provided in the skill directory. The usage of the script can be found below:

```
usage: get_traces.py [-h] --tx-hash TX_HASH --rpc-var RPC_VAR [--label LABEL] [--verbosity VERBOSITY]

options:
  -h, --help            show this help message and exit
  --tx-hash TX_HASH
  --rpc-var RPC_VAR
  --label LABEL         Label in format <address>:name (can be used multiple times)
  --verbosity VERBOSITY
```

Note that the invocation can take a few minutes to run, as transactions have to be processed from their point within the historical block. Meaning all prior transactions must also be processed to ensure the correct chain state prior to the tx invocation. Also note it is possible for the invocation to fail if too many txs are within a block to be processed at once, which can cause a 429 error. If that occurs, retrying until all the prior txs are processed should work. Finally, the output will be printed directly in the terminal, which can be redirected to an output txt file as directed by the user.

For the `--rpc-var` parameter, the following variables may be provided and correspond to environment variables:

```
ETH_MAINNET -- ethereum (eth) network
BASE_MAINNET -- base network
OP_MAINNET -- optimism (op) network
ARB_MAINNET -- arbitrum (arb) network
```

The `--label` paramter allows the user to provide a specific formatting of `<address>:name` to be labeled within the tx trace. This is provided by the user and should not otherwise be generated if the user does not provide anything.

Finally, the `--verbosity` parameter controls the trace output. Certain tx traces can be very complex and contain a large amount of nested calls and traces. This parameter allows traces of an arbitrary depth to be printed, which can help trim the output if it is very long. This is especially important for more complex traces where only high-level calls may be of interested. See the next section for examples.

IMPORTANT: Do not truncate or otherwise modify traces returned by the script. If necessary, use the `--verbosity` flag the limit the depth of traces returned. It is important that the traces remain unmodified (except by using the flag).

## Example

```bash
# Get the transaction traces for hash 0xd813751bfb98a51912b8394b5856ae4515be6a9c6e5583e06b41d9255ba6e3c1 from eth mainnet
uv run scripts/get_traces.py --tx-hash 0xd813751bfb98a51912b8394b5856ae4515be6a9c6e5583e06b41d9255ba6e3c1 --rpc-var ETH_MAINNET

Executing previous transactions from the block.
Traces:
  [936556] 0x2073111E6Ebb6826F7e9c6192C6304Aa5aF5E340::ad24067c()
    ├─ [790933] → new <unknown>@0x08947cedf35f9669012bDA6FdA9d03c399B017Ab
    │   ├─ [7596] 0x3f4D749675B3e48bCCd932033808a7079328Eb48::token() [staticcall]
    │   │   ├─ [2625] RareStakingV1::token() [delegatecall]
    │   │   │   └─ ← [Return] TransparentUpgradeableProxy: [0xba5BDe662c17e2aDFF1075610382B9B691296350]
    │   │   └─ ← [Return] TransparentUpgradeableProxy: [0xba5BDe662c17e2aDFF1075610382B9B691296350]
    │   └─ ← [Return] 3894 bytes of code
    ├─ [13414] 0x08947cedf35f9669012bDA6FdA9d03c399B017Ab::getStakingContractBalance()
    │   ├─ [9873] TransparentUpgradeableProxy::fallback(0x3f4D749675B3e48bCCd932033808a7079328Eb48) [staticcall]
    │   │   ├─ [2542] SuperRareToken::balanceOf(0x3f4D749675B3e48bCCd932033808a7079328Eb48) [delegatecall]
    │   │   │   └─ ← [Return] 11907874713019104529057960 [1.19e25]
    │   │   └─ ← [Return] 11907874713019104529057960 [1.19e25]
    │   └─ ← [Return] 0x00000000000000000000000000000000000000000009d9972e8262b432cd88a8
    ├─ [4414] 0x08947cedf35f9669012bDA6FdA9d03c399B017Ab::getTokenBalance()
    │   ├─ [3373] TransparentUpgradeableProxy::fallback(0x08947cedf35f9669012bDA6FdA9d03c399B017Ab) [staticcall]
    │   │   ├─ [2542] SuperRareToken::balanceOf(0x08947cedf35f9669012bDA6FdA9d03c399B017Ab) [delegatecall]
    │   │   │   └─ ← [Return] 0
    │   │   └─ ← [Return] 0
    │   └─ ← [Return] 0x0000000000000000000000000000000000000000000000000000000000000000
...clipped for brevity

# Get the same traces but with verbosity 1
uv run scripts/get_traces.py --tx-hash 0xd813751bfb98a51912b8394b5856ae4515be6a9c6e5583e06b41d9255ba6e3c1 --rpc-var ETH_MAINNET --verbosity 1

Executing previous transactions from the block.
Traces:
  [936556] 0x2073111E6Ebb6826F7e9c6192C6304Aa5aF5E340::ad24067c()
    ├─ [790933] → new <unknown>@0x08947cedf35f9669012bDA6FdA9d03c399B017Ab
    ├─ [13414] 0x08947cedf35f9669012bDA6FdA9d03c399B017Ab::getStakingContractBalance()
    ├─ [4414] 0x08947cedf35f9669012bDA6FdA9d03c399B017Ab::getTokenBalance()
...clipped for brevity
```
