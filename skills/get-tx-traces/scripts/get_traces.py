# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""
Use subprocess to run the `cast run` command and get the traces.
Users can provide additional arguments to trim the traces to be less verbose.
"""

import argparse
import subprocess
import os

def get_traces(tx_hash, rpc_env_var, labels):
    """
    Use subprocess to run the `cast run` command and get the traces.
    """
    rpc_url = os.getenv(rpc_env_var)
    label_flags = ""
    if labels:
        label_flags = " ".join([f"--label {label}" for label in labels])
    command = f"cast run {tx_hash} --rpc-url {rpc_url} {label_flags}"
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout

def parse_traces(output, verbosity):
    """
    Parse the traces to be less verbose.
    """
    if verbosity is None:
        return output

    new_output = ""
    # For the number of tree depth indicators in the output, print the line if depth is less than verbosity
    for line in output.split("\n"):
        # Count tree depth indicators: │ ├ └
        depth_count = line.count("│") + line.count("├") + line.count("└")

        if depth_count <= verbosity:
            new_output += line + "\n"
    return new_output

if __name__ == "__main__":
    """
    Main function to get the traces.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--tx-hash", type=str, required=True)
    parser.add_argument("--rpc-var", type=str, required=True)
    parser.add_argument("--label", type=str, required=False, action='append', help="Label in format <address>:name (can be used multiple times)")
    parser.add_argument("--verbosity", type=int, required=False)
    args = parser.parse_args()

    tx_hash = args.tx_hash
    rpc_var = args.rpc_var
    labels = args.label
    verbosity = args.verbosity

    # Check if cached traces exist
    if os.path.exists(f"cached/{tx_hash}.txt"):
        with open(f"cached/{tx_hash}.txt", "r") as cache_file:
            traces = cache_file.read()
        print(f"Loaded cached traces from cached/{tx_hash}.txt")
        retrieved_from_cache = True
    else:
        traces = get_traces(tx_hash, rpc_var, labels)
        retrieved_from_cache = False

    # Cache trace output to cached file with tx_hash as name
    if not retrieved_from_cache:
        os.makedirs("cached", exist_ok=True)
        with open(f"cached/{tx_hash}.txt", "w") as cache_file:
            cache_file.write(traces)
            print(f"Cached parsed traces to cached/{tx_hash}.txt")

    parsed_traces = parse_traces(traces, verbosity)
    print(parsed_traces)