# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "requests",
#   "tree-sitter",
#   "tree-sitter-solidity",
# ]
# ///

"""
Retrieves the source code of a contract given its address and the chain it is on.
Uses the Etherscan API to get the source code.
"""

import argparse
import os
import requests
import sys
import json
import re
import warnings

from tree_sitter import Language, Parser
import tree_sitter_solidity as TSSolidity

CHAIN_TO_ID = {
    "eth": "1",
    "op": "10",
    "arb": "42161",
    "base": "8453",
}

def combine_sources(sources):
    """
    Combines the sources into a single source code string.
    """
    # Pattern to match contract definitions: "contract <name> {" or "abstract contract <name> is ... {" or "library <name> {"
    # Note: abstract must come before contract in alternation
    # This pattern handles inheritance (e.g., "contract Foo is Bar {")
    # Captures: group(1) = type (library/contract/abstract contract), group(2) = name
    contract_pattern = re.compile(r'\b(abstract\s+contract|contract|library)\s+(\w+)(?:\s+is\s+[^{]+)?\s*\{')

    combined_source = ""
    for source_key, source_content in sources['sources'].items():
        # Parse the source key for the file name
        file_name = source_key.split('/')[-1]
        content = source_content['content']

        # Skip common dependency libraries (but not all lib directories, as some contracts have source in lib/)
        skip_lib_patterns = [
            'lib/openzeppelin',
            'lib/forge-std',
            'lib/ds-test',
            'lib/solmate',
            'lib/safe-contracts',
            'lib/prb-math'
        ]
        if any(source_key.startswith(pattern) for pattern in skip_lib_patterns):
            continue

        # Skip files containing 'openzeppelin' in the path
        if 'openzeppelin' in source_key.lower():
            continue

        # Skip files starting with 'EIP' or 'ERC' (standard implementations/interfaces)
        if file_name.startswith(('EIP', 'ERC')):
            continue

        # If the file name starts with an 'I' and
        # the content does not include a contract definition, then skip it (likely an interface)
        if file_name.startswith('I') and not contract_pattern.search(content):
            continue

        # Otherwise, add the source to the sources dictionary
        combined_source += content + "\n"

    return combined_source

def parse_source(response):
    """
    Parses the sources from the response.
    Handles Etherscan's double-wrapped JSON format for multi-file contracts.
    Also handles single-file contracts.
    """
    if response.get('status') == '1' and response.get('result'):
        result = response['result'][0]
        source_code = result.get('SourceCode', '')

        # Etherscan wraps multi-file sources in double braces {{ ... }}
        if source_code.startswith('{{') and source_code.endswith('}}'):
            # Remove outer braces and parse the inner JSON
            source_code = source_code[1:-1]
            try:
                parsed_source = json.loads(source_code)
                result['SourceCode'] = parsed_source
            except json.JSONDecodeError:
                # If parsing fails, keep original
                raise ValueError(f"Failed to parse source code: {source_code} ")
        elif source_code.startswith('{'):
            # Try to parse as regular JSON
            try:
                parsed_source = json.loads(source_code)
                result['SourceCode'] = parsed_source
            except json.JSONDecodeError:
                # If parsing fails, keep original (might be single-file source)
                raise ValueError(f"Failed to parse source code: {source_code} ")

        # Check if SourceCode is a dict with 'sources' key (multi-file) or a plain string (single-file)
        if isinstance(result['SourceCode'], dict) and 'sources' in result['SourceCode']:
            return combine_sources(result['SourceCode'])
        else:
            # Single-file contract - return the source code as-is
            return result['SourceCode']

    return ""

def find_nodes_by_type(node, node_type):
    """
    Recursively finds all nodes of a given type in the tree.
    """
    results = []
    if node.type == node_type:
        results.append(node)
    for child in node.children:
        results.extend(find_nodes_by_type(child, node_type))
    return results

def parse_relevant_source(source_code, traces):
    """
    Given the function call traces, only return source code from functions that are called in the traces.
    This includes any internal functions called by the functions in the traces.
    """
    # Parse the combined source code using tree-sitter-solidity
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', DeprecationWarning)
        language = Language(TSSolidity.language())
    parser = Parser(language)
    tree = parser.parse(source_code.encode('utf-8'))
    root_node = tree.root_node

    functions = {}
    internal_functions = set()
    relevant_functions = set()
    # Find all the external or public function declarations in the source code
    function_declarations = find_nodes_by_type(root_node, "function_definition")
    for function_declaration in function_declarations:
        function_code = function_declaration.text.decode('utf-8').strip()
        # Extract the function name between "function" and "("
        name_match = re.search(r'function\s+([A-Za-z0-9_]+)\s*\(', function_code)
        function_name = name_match.group(1) if name_match else None

        # Extract the visibility of the function (search between ')' and '{')
        signature_match = re.search(r'\)\s*([^{]*)\{', function_code)
        visibility = None
        if signature_match:
            modifiers = signature_match.group(1)
            visibility_match = re.search(r'\b(public|external|internal|private)\b', modifiers)
            visibility = visibility_match.group(1) if visibility_match else None

        # Add all functions to the directory with indiciation if they are external or internal
        is_external = visibility and visibility.lower() in ["public", "external"]
        if not is_external:
            internal_functions.add(function_name)

        functions[function_name] = {
            "code": function_code,
            "is_external": is_external,
            "internal_calls": set(),
        }

    # For each external or public function in the source code, check if it is called in the traces
    # External function calls would be of the form `::function_name(...)` or `::function_name{value: ...}(...)`
    # which can be parsed using a regex. The {value: ...} modifier appears when ETH is sent with the call.
    for function_name in functions:
        if functions[function_name]["is_external"]:
            # Check if the function is called in the traces using the pattern ::<function_name> or ::<function_name>{...}
            # Allow optional modifiers like {value: ...} between function name and opening parenthesis
            if re.search(rf'::{function_name}(?:\{{[^}}]*\}})?\(', traces):
                # Add the function to the relevant functions set
                relevant_functions.add(function_name)

    # Iteratively find all functions called by relevant functions (including nested calls)
    # Keep iterating until no new functions are found
    # Note: We iterate through all functions not just internal functions
    previous_size = 0
    while len(relevant_functions) > previous_size:
        previous_size = len(relevant_functions)

        for function_name in functions:
            # Skip if already in relevant functions
            if function_name in relevant_functions:
                continue

            # Check if the function is called by any function in relevant_functions
            # Use word boundaries to avoid partial matches
            pattern = rf'\b{re.escape(function_name)}\s*\('
            if any(re.search(pattern, functions[func]["code"]) for func in relevant_functions):
                # Add the function to the relevant functions set
                relevant_functions.add(function_name)

    # For all the identified function calls, return the source code for its function and any internal functions called by it
    return "\n".join([functions[func]["code"] for func in relevant_functions])

def get_source(address, chain, traces=None):
    """
    Retrieves the source code of a contract given its address and the chain it is on.
    """
    api_key = os.getenv('ETHERSCAN_API_KEY')
    if not api_key:
        raise ValueError("ETHERSCAN_API_KEY is not set")
    url = f"https://api.etherscan.io/v2/api?module=contract&action=getsourcecode&address={address}&chainid={chain}&apikey={api_key}"
    response = requests.get(url)
    source_code = parse_source(response.json())
    if traces:
        # Parse the traces to get the relevant functions called from the source code, only return that code and any
        # internal functions called.
        return parse_relevant_source(source_code, traces)
    else:
        return source_code

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Get the source code of a contract given its address and the chain it is on.')
    parser.add_argument('address', type=str, nargs='+', help='The address(es) of the contract(s). Multiple addresses can be provided (space or comma-separated) and their source code will be aggregated.')
    parser.add_argument('chain', type=str, help='The chain the contract is on')
    parser.add_argument('--traces', type=str, help='The path to a traces file for a hack involving the contract')
    args = parser.parse_args()
    chain_id = CHAIN_TO_ID[args.chain]
    traces = args.traces
    if traces:
        with open(traces, 'r') as file:
            traces = file.read()

    # Handle comma-separated addresses by splitting them
    addresses = []
    for addr in args.address:
        # Split by comma and strip whitespace, filter out empty strings
        addresses.extend([a.strip() for a in addr.split(',') if a.strip()])

    print("Parsing addresses:", ", ".join(addresses))

    # Get source code for all addresses and aggregate
    aggregated_source = ""
    for address in addresses:
        if traces:
            source = get_source(address, chain_id, traces)
        else:
            source = get_source(address, chain_id)

        if source:
            aggregated_source += source + "\n\n"

    print(aggregated_source.strip())
