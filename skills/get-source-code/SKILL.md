---
name: get-source-code
description: Get source code for a smart contract given its contract address
---

# Get source code

## Prerequisites

- `uv` must be installed. It is used to run the script and automatically manage its dependencies. Installation instructions: https://docs.astral.sh/uv/getting-started/installation/
- `ETHERSCAN_API_KEY` must be set as an environment variable. The script uses this key to authenticate requests to the Etherscan API. If it is not set, the script will exit with an error.

This skill enables the retrieval of source code for a smart contract given its contract address. The user is expected to provide the contract address as well as the chain where the contract has been deployed to. To retrieve the source code, the script `get_source.py` is provided in the skill's `scripts` directory. The usage of the script can be found below:

```
usage: uv run get_source.py [-h] [--traces TRACES] address [address ...] chain

Get the source code of a contract given its address and the chain it is on.

positional arguments:
  address          The address(es) of the contract(s). Multiple addresses can be provided (space or comma-separated) and their source code
                   will be aggregated.
  chain            The chain the contract is on

options:
  -h, --help       show this help message and exit
  --traces TRACES  The path to a traces file for a hack involving the contract
```

One or more addresses can be provided as a comma-delimited list or space-delimited. For the `chain` positional argument, the following networks are available:

```
eth -- Ethereum
op -- Optimism
arb -- Arbitrum
base -- Base
```

The `--traces` optional argument enables the script to parse out source code that is relevant with respect to a provided file that contains the transaction (tx) traces. If a traces file is available, then the optional argument should always be provided in order to ensure only the most relevant source code is retrieved.

Finally, the output will be printed directly in the terminal, which can be redirected to an output txt file as directed by the user.

IMPORTANT: Do not truncate or otherwise modify the source code directly. No modifications or annotations should be added separately.

## Examples

```bash
# Get the full source code for contract address `0xA88800CD213dA5Ae406ce248380802BD53b47647` from eth mainnet
uv run scripts/get_source.py 0xA88800CD213dA5Ae406ce248380802BD53b47647 eth

# Get only the relevant source code given a traces file `traces.txt`
uv run scripts/get_source.py 0xA88800CD213dA5Ae406ce248380802BD53b47647 eth --traces traces.txt
```
