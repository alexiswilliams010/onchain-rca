"""Tests for manage_traces.py — runs against test_trace.txt fixture."""

import argparse
import os
import shutil
import textwrap

import pytest

import manage_traces as mt

FIXTURE = os.path.join(os.path.dirname(__file__), "test_trace.txt")


@pytest.fixture
def trace_text():
    with open(FIXTURE) as f:
        return f.read()


@pytest.fixture
def trace_lines(trace_text):
    return trace_text.split("\n")


# ── compute_depth ──────────────────────────────────────────────────────────


class TestComputeDepth:
    def test_no_indicators(self):
        assert mt.compute_depth("Traces:") == 0
        assert mt.compute_depth("") == 0

    def test_root_trace_line(self):
        line = "  [173270] 0x6f95::borrow(60384500431 [6.038e10])"
        assert mt.compute_depth(line) == 0

    def test_depth_one(self):
        line = "    \u251c\u2500 [168056] 0x67Db::borrow() [delegatecall]"
        assert mt.compute_depth(line) == 1

    def test_depth_two(self):
        line = "    \u2502   \u251c\u2500 [12708] Unitroller::fallback()"
        assert mt.compute_depth(line) == 2

    def test_depth_three(self):
        line = "    \u2502   \u2502   \u251c\u2500 [7565] Foo::bar() [delegatecall]"
        assert mt.compute_depth(line) == 3

    def test_closing_branch(self):
        line = "    \u2502   \u2502   \u2514\u2500 \u2190 [Return] 0"
        assert mt.compute_depth(line) == 3

    def test_fixture_depths(self, trace_lines):
        """Verify depths match expected for key lines in fixture."""
        # "Traces:" header has depth 0
        assert mt.compute_depth(trace_lines[1]) == 0
        # Root call line — no tree chars
        assert mt.compute_depth(trace_lines[2]) == 0
        # First ├─ child
        assert mt.compute_depth(trace_lines[3]) == 1


# ── decode_hex_word ────────────────────────────────────────────────────────


class TestDecodeHexWord:
    def test_zero(self):
        assert mt.decode_hex_word("0" * 64) == "0"

    def test_address(self):
        word = "000000000000000000000000b5711daec960c9487d95ba327c570a7cce4982c0"
        assert mt.decode_hex_word(word) == "0xb5711daec960c9487d95ba327c570a7cce4982c0"

    def test_small_uint(self):
        word = "00000000000000000000000000000000000000000000000000000002e6ca3d59"
        assert mt.decode_hex_word(word) == "12461948249"

    def test_large_uint_not_address(self):
        # Top bytes non-zero — not an address pattern
        word = "0000000000000000000000000000000000000000000000002d0ca45d09c36880"
        assert mt.decode_hex_word(word) == str(int(word, 16))

    def test_full_nonzero_uint(self):
        word = "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"
        result = mt.decode_hex_word(word)
        assert result == str(2**256 - 1)


# ── decode_hex_data ────────────────────────────────────────────────────────


class TestDecodeHexData:
    def test_single_zero_word(self):
        assert mt.decode_hex_data("0" * 64) == "0"

    def test_single_address_word(self):
        data = "000000000000000000000000ae7ab96520de3a18e5e111b5eaab095312d7fe84"
        assert mt.decode_hex_data(data) == "0xae7ab96520de3a18e5e111b5eaab095312d7fe84"

    def test_multi_word(self):
        data = (
            "000000000000000000000000b5711daec960c9487d95ba327c570a7cce4982c0"
            "000000000000000000000000ae7ab96520de3a18e5e111b5eaab095312d7fe84"
            "00000000000000000000000000000000000000000000000000000000693bcb80"
            "0000000000000000000000000000000000000000000000002d0ca45d09c36880"
        )
        result = mt.decode_hex_data(data)
        parts = result.split(", ")
        assert len(parts) == 4
        assert parts[0] == "0xb5711daec960c9487d95ba327c570a7cce4982c0"
        assert parts[1] == "0xae7ab96520de3a18e5e111b5eaab095312d7fe84"
        assert parts[2] == "1765526400"
        assert parts[3] == str(int("2d0ca45d09c36880", 16))

    def test_not_multiple_of_64(self):
        data = "abcdef"
        assert mt.decode_hex_data(data) == data

    def test_empty(self):
        assert mt.decode_hex_data("") == ""


# ── decode_line ────────────────────────────────────────────────────────────


class TestDecodeLine:
    def test_raw_hex_return_zero(self):
        line = "    \u2502   \u2502   \u2514\u2500 \u2190 [Return] 0x0000000000000000000000000000000000000000000000000000000000000000"
        result = mt.decode_line(line)
        assert result.endswith("\u2190 [Return] 0")
        assert "0x000" not in result

    def test_raw_hex_return_uint(self):
        line = "    \u2502   \u2502   \u2514\u2500 \u2190 [Return] 0x00000000000000000000000000000000000000000000000000000002e6ca3d59"
        result = mt.decode_line(line)
        assert "12461948249" in result

    def test_raw_hex_return_address(self):
        line = "    \u2514\u2500 \u2190 [Return] 0x000000000000000000000000b5711daec960c9487d95ba327c570a7cce4982c0"
        result = mt.decode_line(line)
        assert "0xb5711daec960c9487d95ba327c570a7cce4982c0" in result

    def test_raw_hex_params(self):
        line = "    \u251c\u2500 [116333] 0x1A7e::3027fe66(0000000000000000000000000000000000000000000000002d0ca45d09c3688000000000000000000000000000000000000000000000000000000000693bcb80000000000000000000000000ae7ab96520de3a18e5e111b5eaab095312d7fe84)"
        result = mt.decode_line(line)
        assert "::3027fe66(" in result
        assert "1765526400" in result
        assert "0xae7ab96520de3a18e5e111b5eaab095312d7fe84" in result
        # Should not contain raw hex blob
        assert "0000000000000000" not in result

    def test_already_decoded_params_untouched(self):
        line = "  [173270] 0x6f95::borrow(60384500431 [6.038e10])"
        assert mt.decode_line(line) == line

    def test_already_decoded_return_untouched(self):
        line = "    \u2502   \u2502   \u2514\u2500 \u2190 [Return] 60384500431 [6.038e10]"
        assert mt.decode_line(line) == line

    def test_stop_untouched(self):
        line = "    \u2502   \u2502   \u2514\u2500 \u2190 [Stop]"
        assert mt.decode_line(line) == line

    def test_revert_untouched(self):
        line = "    \u2502   \u2502   \u2514\u2500 \u2190 [Revert] EvmError: Revert"
        assert mt.decode_line(line) == line

    def test_return_true_untouched(self):
        line = "    \u2502   \u2502   \u2514\u2500 \u2190 [Return] true"
        assert mt.decode_line(line) == line

    def test_short_hex_return_untouched(self):
        # 40-char hex (raw address) — not 64+ so left alone
        line = "    \u2514\u2500 \u2190 [Return] 0xae7ab96520DE3A18E5e111B5EaAb095312D7fE84"
        assert mt.decode_line(line) == line

    def test_fallback_with_0x_prefix_untouched(self):
        line = "    \u251c\u2500 Proxy::fallback(0x7e8ef7e9000000000000000000000000b5711daec960c9487d95ba327c570a7cce4982c0)"
        # Has 0x prefix inside parens, so the pure-hex regex won't match
        assert mt.decode_line(line) == line


# ── filter_by_depth ────────────────────────────────────────────────────────


class TestFilterByDepth:
    def test_depth_zero(self, trace_lines):
        result = mt.filter_by_depth(trace_lines, 0)
        for line in result:
            assert mt.compute_depth(line) == 0

    def test_depth_one(self, trace_lines):
        result = mt.filter_by_depth(trace_lines, 1)
        for line in result:
            assert mt.compute_depth(line) <= 1
        # Should include more lines than depth=0
        depth0 = mt.filter_by_depth(trace_lines, 0)
        assert len(result) > len(depth0)

    def test_large_depth_returns_all(self, trace_lines):
        result = mt.filter_by_depth(trace_lines, 100)
        assert len(result) == len(trace_lines)


# ── extract_subtree ────────────────────────────────────────────────────────


class TestExtractSubtree:
    def test_root_call_captures_all_trace(self, trace_lines):
        # Line 2 is the root trace call (depth 0)
        # Its subtree should include everything until the next depth-0 line
        root_idx = 2
        subtree = mt.extract_subtree(trace_lines, root_idx)
        assert subtree[0] == trace_lines[root_idx]
        assert len(subtree) > 1
        # All subsequent lines should have greater depth
        root_depth = mt.compute_depth(subtree[0])
        for line in subtree[1:]:
            assert mt.compute_depth(line) > root_depth

    def test_leaf_node(self, trace_lines):
        # Find a └─ line (leaf); subtree should be just that line
        for i, line in enumerate(trace_lines):
            if "\u2514\u2500 \u2190 [Stop]" in line:
                subtree = mt.extract_subtree(trace_lines, i)
                assert len(subtree) == 1
                break


# ── filter_by_call ─────────────────────────────────────────────────────────


class TestFilterByCall:
    def test_borrow(self, trace_lines):
        result = mt.filter_by_call(trace_lines, "borrow")
        # Should find the root borrow call
        assert any("::borrow(" in l for l in result)
        # Inner delegatecall borrow is part of the outer subtree
        assert len(result) > 2

    def test_borrow_with_depth(self, trace_lines):
        result = mt.filter_by_call(trace_lines, "borrow", max_depth=0)
        # Only the root borrow line itself (relative depth 0)
        assert len(result) == 1
        assert "::borrow(" in result[0]

    def test_borrow_depth_one(self, trace_lines):
        result = mt.filter_by_call(trace_lines, "borrow", max_depth=1)
        root_depth = mt.compute_depth(result[0])
        for line in result:
            assert mt.compute_depth(line) - root_depth <= 1

    def test_no_duplicates_nested(self, trace_lines):
        """Nested borrow calls shouldn't produce duplicate output."""
        result = mt.filter_by_call(trace_lines, "borrow")
        # The outer borrow's subtree already contains the inner borrow,
        # so total lines should equal the outer subtree size
        root_idx = next(i for i, l in enumerate(trace_lines) if "::borrow(" in l)
        expected = mt.extract_subtree(trace_lines, root_idx)
        assert len(result) == len(expected)

    def test_nonexistent_call(self, trace_lines):
        result = mt.filter_by_call(trace_lines, "nonexistent_function")
        assert result == []

    def test_balanceOf(self, trace_lines):
        result = mt.filter_by_call(trace_lines, "balanceOf")
        assert len(result) > 0
        assert all("::balanceOf(" in l or mt.compute_depth(l) > 0 for l in result)

    def test_transfer(self, trace_lines):
        result = mt.filter_by_call(trace_lines, "transfer")
        assert any("::transfer(" in l for l in result)


# ── filter_by_address ──────────────────────────────────────────────────────


class TestFilterByAddress:
    # 0x912f... appears in borrowAllowed, transfer, and emit Borrow
    ADDR = "0x912f8C412fF54a8773eE54a826142876077e9501"

    def test_finds_address(self, trace_lines):
        result = mt.filter_by_address(trace_lines, self.ADDR)
        assert len(result) > 0
        # At least one line should contain the address
        assert any(self.ADDR.lower() in l.lower() for l in result)

    def test_case_insensitive(self, trace_lines):
        lower = mt.filter_by_address(trace_lines, self.ADDR.lower())
        upper = mt.filter_by_address(trace_lines, self.ADDR.upper())
        assert lower == upper

    def test_with_depth_one(self, trace_lines):
        result = mt.filter_by_address(trace_lines, self.ADDR, max_depth=1)
        # Each matched subtree clipped to 1 level
        assert len(result) > 0
        full = mt.filter_by_address(trace_lines, self.ADDR)
        assert len(result) <= len(full)

    def test_with_depth_zero(self, trace_lines):
        result = mt.filter_by_address(trace_lines, self.ADDR, max_depth=0)
        # Only the matched lines themselves
        for line in result:
            assert self.ADDR.lower() in line.lower()

    def test_no_duplicates(self, trace_lines):
        result = mt.filter_by_address(trace_lines, self.ADDR)
        # No exact duplicate lines from overlapping subtrees
        # (lines at different depths could look similar but aren't exact dupes)
        seen_indices = []
        for line in result:
            idx = trace_lines.index(line)
            assert idx not in seen_indices or trace_lines.count(line) > 1
            seen_indices.append(idx)

    def test_nonexistent_address(self, trace_lines):
        result = mt.filter_by_address(trace_lines, "0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef")
        assert result == []


# ── filter_by_contract ─────────────────────────────────────────────────────


class TestFilterByContract:
    def test_unitroller(self, trace_lines):
        result = mt.filter_by_contract(trace_lines, "Unitroller")
        assert len(result) > 0
        assert any("Unitroller::" in l for l in result)

    def test_includes_subtree(self, trace_lines):
        result = mt.filter_by_contract(trace_lines, "Unitroller")
        # First Unitroller call has children (delegatecall inside)
        assert len(result) > 1

    def test_case_insensitive(self, trace_lines):
        lower = mt.filter_by_contract(trace_lines, "unitroller")
        upper = mt.filter_by_contract(trace_lines, "UNITROLLER")
        assert lower == upper
        assert len(lower) > 0

    def test_fiat_token(self, trace_lines):
        result = mt.filter_by_contract(trace_lines, "FiatTokenV2_2")
        assert len(result) > 0
        assert any("FiatTokenV2_2::" in l for l in result)

    def test_with_depth_zero(self, trace_lines):
        result = mt.filter_by_contract(trace_lines, "Unitroller", max_depth=0)
        # Only the Unitroller:: lines themselves
        for line in result:
            assert "unitroller::" in line.lower()

    def test_with_depth_one(self, trace_lines):
        result = mt.filter_by_contract(trace_lines, "Unitroller", max_depth=1)
        full = mt.filter_by_contract(trace_lines, "Unitroller")
        assert len(result) <= len(full)
        assert len(result) > 0

    def test_nonexistent(self, trace_lines):
        result = mt.filter_by_contract(trace_lines, "NonExistentContract")
        assert result == []

    def test_no_duplicates_nested(self, trace_lines):
        """Nested matches shouldn't produce duplicate lines."""
        result = mt.filter_by_contract(trace_lines, "Unitroller")
        # The first Unitroller subtree may contain another Unitroller call;
        # the covered set should prevent double-counting
        idx_first = next(i for i, l in enumerate(trace_lines) if "Unitroller::" in l)
        outer_subtree = mt.extract_subtree(trace_lines, idx_first)
        # If there are nested Unitroller calls, result should equal
        # the outer subtree (inner ones are covered)
        inner_count = sum(1 for l in outer_subtree if "Unitroller::" in l)
        if inner_count > 1:
            assert len(result) == len(outer_subtree)


# ── filter_by_selector ────────────────────────────────────────────────────


class TestFilterBySelector:
    """Test against the 0xb73 trace which has hex selectors like 3027fe66."""

    @pytest.fixture
    def b73_lines(self):
        path = os.path.join(os.path.dirname(__file__),
                            "..", "cached",
                            "0xb73e45948f4aabd77ca888710d3685dd01f1c81d24361d4ea0e4b4899d490e1e.txt")
        if not os.path.exists(path):
            pytest.skip("0xb73 cached trace not available")
        with open(path) as f:
            return f.read().split("\n")

    def test_finds_selector(self, b73_lines):
        result = mt.filter_by_selector(b73_lines, "3027fe66")
        assert len(result) > 0
        assert any("::3027fe66(" in l for l in result)

    def test_with_0x_prefix(self, b73_lines):
        without = mt.filter_by_selector(b73_lines, "3027fe66")
        with_prefix = mt.filter_by_selector(b73_lines, "0x3027fe66")
        assert without == with_prefix

    def test_case_insensitive(self, b73_lines):
        lower = mt.filter_by_selector(b73_lines, "3027fe66")
        upper = mt.filter_by_selector(b73_lines, "3027FE66")
        assert lower == upper

    def test_includes_subtree(self, b73_lines):
        result = mt.filter_by_selector(b73_lines, "3027fe66")
        # The 3027fe66 calls have children
        assert len(result) > 1

    def test_with_depth_zero(self, b73_lines):
        result = mt.filter_by_selector(b73_lines, "3027fe66", max_depth=0)
        for line in result:
            assert "::3027fe66(" in line.lower()

    def test_with_depth_one(self, b73_lines):
        result = mt.filter_by_selector(b73_lines, "3027fe66", max_depth=1)
        full = mt.filter_by_selector(b73_lines, "3027fe66")
        assert 0 < len(result) <= len(full)

    def test_7e8ef7e9(self, b73_lines):
        result = mt.filter_by_selector(b73_lines, "7e8ef7e9")
        assert len(result) > 0
        assert any("::7e8ef7e9(" in l for l in result)

    def test_nonexistent(self, b73_lines):
        result = mt.filter_by_selector(b73_lines, "deadbeef")
        assert result == []

    def test_works_on_small_trace(self, trace_lines):
        """The 0x889 trace has no hex selectors, so should return empty."""
        result = mt.filter_by_selector(trace_lines, "3027fe66")
        assert result == []


# ── discover_contracts ─────────────────────────────────────────────────────


class TestDiscoverContracts:
    def test_finds_all_contracts(self, trace_lines):
        result = mt.discover_contracts(trace_lines)
        # Should find both address-based and name-based contracts
        addresses = [v["address"] for v in result.values() if v["address"]]
        names = [v["name"] for v in result.values() if v["name"]]
        assert "0x6f95d4d251053483f41c8718C30F4F3C404A8cf2" in addresses
        assert "Unitroller" in names
        assert "FiatTokenV2_2" in names

    def test_functions_per_contract(self, trace_lines):
        result = mt.discover_contracts(trace_lines)
        # Find the 0xd134... contract — has multiple delegatecall functions
        key = ("0xd13457c3532d00b1e581596c191c2b5e215e3b9b".lower(), None)
        assert key in result
        funcs = [f for f, _ in result[key]["functions"]]
        assert "_beforeNonReentrant" in funcs
        assert "borrowAllowed" in funcs
        assert "borrowWithinLimits" in funcs
        assert "_afterNonReentrant" in funcs

    def test_no_duplicate_functions(self, trace_lines):
        result = mt.discover_contracts(trace_lines)
        for info in result.values():
            func_names = [f for f, _ in info["functions"]]
            assert len(func_names) == len(set(func_names))

    def test_preserves_call_order(self, trace_lines):
        result = mt.discover_contracts(trace_lines)
        # First contract should be the root caller
        first = list(result.values())[0]
        assert first["address"] == "0x6f95d4d251053483f41c8718C30F4F3C404A8cf2"

    def test_decoded_vs_selector_types(self):
        """Hex selectors are tagged as 'selector', decoded names as 'decoded'."""
        lines = [
            "  [100] 0xABC::transfer()",
            "  [100] 0xABC::0a1b2c3d()",
        ]
        result = mt.discover_contracts(lines)
        key = ("0xabc", None)
        funcs = result[key]["functions"]
        assert ("transfer", "decoded") in funcs
        assert ("0a1b2c3d", "selector") in funcs

    def test_empty_trace(self):
        result = mt.discover_contracts(["", "Traces:", ""])
        assert len(result) == 0


class TestDiscoverWithB73:
    """Discover tests against the larger 0xb73 trace with hex selectors."""

    @pytest.fixture
    def b73_lines(self):
        path = os.path.join(os.path.dirname(__file__),
                            "..", "cached",
                            "0xb73e45948f4aabd77ca888710d3685dd01f1c81d24361d4ea0e4b4899d490e1e.txt")
        if not os.path.exists(path):
            pytest.skip("0xb73 cached trace not available")
        with open(path) as f:
            return f.read().split("\n")

    def test_finds_hex_selectors(self, b73_lines):
        result = mt.discover_contracts(b73_lines)
        # 0x4BFD... has selector b48dc7a7
        key = ("0x4bfd5c65082171df83fd0fbbe54aa74909529b2c", None)
        assert key in result
        funcs = result[key]["functions"]
        assert ("b48dc7a7", "selector") in funcs

    def test_finds_decoded_names(self, b73_lines):
        result = mt.discover_contracts(b73_lines)
        names = [v["name"] for v in result.values() if v["name"]]
        assert "Oracle" in names
        assert "Otoken" in names

    def test_oracle_functions(self, b73_lines):
        result = mt.discover_contracts(b73_lines)
        key = (None, "Oracle")
        assert key in result
        funcs = [f for f, _ in result[key]["functions"]]
        assert "getPrice" in funcs
        assert "getPricer" in funcs
        assert "setExpiryPrice" in funcs

    def test_mixed_decoded_and_selectors(self, b73_lines):
        result = mt.discover_contracts(b73_lines)
        # 0xa4aC... has both decoded functions and hex selectors
        key = ("0xa4ac089b972206021eceb50a494d60b1c74e534e", None)
        assert key in result
        funcs = result[key]["functions"]
        types = {t for _, t in funcs}
        assert "decoded" in types
        assert "selector" in types


class TestFormatDiscover:
    def test_address_only(self):
        contracts = mt.discover_contracts([
            "  [100] 0xABC::foo()",
        ])
        out = mt.format_discover(contracts)
        assert "0xABC" in out
        assert "  foo" in out

    def test_name_only(self):
        contracts = mt.discover_contracts([
            "  [100] MyContract::bar()",
        ])
        out = mt.format_discover(contracts)
        assert "MyContract" in out
        assert "  bar" in out

    def test_selector_prefixed_with_0x(self):
        contracts = mt.discover_contracts([
            "  [100] 0xABC::deadbeef()",
        ])
        out = mt.format_discover(contracts)
        assert "  0xdeadbeef" in out

    def test_empty(self):
        out = mt.format_discover({})
        assert out == ""


class TestCmdDiscoverIntegration:
    TX_HASH = "0xTEST_DISCOVER"

    @pytest.fixture(autouse=True)
    def setup_cache(self, tmp_path, monkeypatch, trace_text):
        cache_dir = tmp_path / "cached"
        cache_dir.mkdir()
        (cache_dir / f"{self.TX_HASH}.txt").write_text(trace_text)
        monkeypatch.chdir(tmp_path)

    def test_output_contains_contracts(self, capsys):
        args = argparse.Namespace(tx_hash=self.TX_HASH)
        mt.cmd_discover(args)
        out = capsys.readouterr().out
        assert "Unitroller" in out
        assert "FiatTokenV2_2" in out
        assert "borrow" in out
        assert "balanceOf" in out

    def test_missing_hash(self):
        with pytest.raises(SystemExit):
            args = argparse.Namespace(tx_hash="0xNONEXISTENT")
            mt.cmd_discover(args)


# ── cmd_show integration ──────────────────────────────────────────────────


class TestCmdShowIntegration:
    """Integration tests that invoke cmd_show via a temp cached directory."""

    TX_HASH = "0xTEST"

    @pytest.fixture(autouse=True)
    def setup_cache(self, tmp_path, monkeypatch, trace_text):
        """Set up a temp cached dir and chdir into it."""
        cache_dir = tmp_path / "cached"
        cache_dir.mkdir()
        (cache_dir / f"{self.TX_HASH}.txt").write_text(trace_text)
        monkeypatch.chdir(tmp_path)

    def _make_args(self, **kwargs):
        defaults = {
            "tx_hash": self.TX_HASH,
            "depth": None,
            "raw": False,
            "call": None,
            "address": None,
            "contract": None,
            "selector": None,
        }
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_show_raw(self, capsys, trace_text):
        mt.cmd_show(self._make_args(raw=True))
        out = capsys.readouterr().out
        # Raw output should preserve hex return values
        assert "0x00000000000000000000000000000000000000000000000000000002e6ca3d59" in out

    def test_show_decoded(self, capsys):
        mt.cmd_show(self._make_args())
        out = capsys.readouterr().out
        # Hex return values should be decoded
        assert "12461948249" in out
        # Already-decoded values should still be present
        assert "60384500431 [6.038e10]" in out

    def test_show_depth(self, capsys):
        mt.cmd_show(self._make_args(depth=1, raw=True))
        out = capsys.readouterr().out
        for line in out.split("\n"):
            assert mt.compute_depth(line) <= 1

    def test_show_call(self, capsys):
        mt.cmd_show(self._make_args(call="borrow"))
        out = capsys.readouterr().out
        assert "::borrow(" in out
        # Should NOT contain header/footer metadata
        assert "Transaction successfully executed" not in out

    def test_show_address(self, capsys):
        addr = "0x912f8C412fF54a8773eE54a826142876077e9501"
        mt.cmd_show(self._make_args(address=addr))
        out = capsys.readouterr().out
        assert addr in out

    def test_show_contract(self, capsys):
        mt.cmd_show(self._make_args(contract="Unitroller"))
        out = capsys.readouterr().out
        assert "Unitroller::" in out
        assert "Transaction successfully executed" not in out

    def test_show_missing_hash(self):
        with pytest.raises(SystemExit):
            mt.cmd_show(self._make_args(tx_hash="0xNONEXISTENT"))


# ── cmd_get integration ───────────────────────────────────────────────────


class TestCmdGetIntegration:
    TX_HASH = "0xTEST_GET"

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

    def test_already_cached(self, tmp_path, capsys):
        cache_dir = tmp_path / "cached"
        cache_dir.mkdir()
        cached_file = cache_dir / f"{self.TX_HASH}.txt"
        cached_file.write_text("existing traces")

        args = argparse.Namespace(tx_hash=self.TX_HASH, rpc_var="ETH_MAINNET", label=None)
        mt.cmd_get(args)
        out = capsys.readouterr().out
        assert "already cached" in out
