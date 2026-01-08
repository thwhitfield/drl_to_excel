"""Tests for Excel writer."""

import pytest
from pathlib import Path
import tempfile
from drl_to_excel.excel_writer import ExcelWriter, write_excel
from drl_to_excel.excel_parser import parse_excel
from drl_to_excel.ir import (
    RuleSet, Rule, FactPattern, Action, ActionType,
    SimpleCondition, RangeCondition, Operator,
)


class TestExcelWriterBasic:
    """Test basic Excel writing functionality."""

    def test_writes_file(self):
        ruleset = RuleSet(
            name="TestRules",
            package="com.example.test",
            rules=[
                Rule(
                    name="Rule1",
                    fact_patterns=[
                        FactPattern(
                            fact_type="Transaction",
                            binding="tx",
                            conditions=[
                                SimpleCondition(
                                    field="score",
                                    operator=Operator.GT,
                                    value=0.8
                                )
                            ]
                        )
                    ],
                    actions=[
                        Action(
                            action_type=ActionType.SET_FIELD,
                            target="decision",
                            value="DECLINE",
                            binding="result"
                        )
                    ]
                )
            ]
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            output_path = Path(f.name)

        try:
            write_excel(ruleset, output_path)
            assert output_path.exists()
            assert output_path.stat().st_size > 0
        finally:
            output_path.unlink()

    def test_writes_package(self):
        ruleset = RuleSet(
            name="TestRules",
            package="com.example.test",
            rules=[
                Rule(
                    name="Rule1",
                    fact_patterns=[
                        FactPattern(
                            fact_type="Transaction",
                            binding="tx",
                            conditions=[
                                SimpleCondition(
                                    field="score",
                                    operator=Operator.GT,
                                    value=0.8
                                )
                            ]
                        )
                    ],
                    actions=[]
                )
            ]
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            output_path = Path(f.name)

        try:
            write_excel(ruleset, output_path)
            # Parse it back
            parsed = parse_excel(output_path)
            assert parsed.package == "com.example.test"
        finally:
            output_path.unlink()


class TestExcelWriterRoundtrip:
    """Test roundtrip: Excel → IR → Excel preserves data."""

    @pytest.fixture
    def fixtures_dir(self):
        return Path(__file__).parent / "fixtures"

    def test_roundtrip_simple_rules(self, fixtures_dir):
        """Excel → IR → Excel → IR should preserve rule structure."""
        original_path = fixtures_dir / "score_rules.xlsx"

        # Parse original
        original = parse_excel(original_path)

        # Write to new file
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            output_path = Path(f.name)

        try:
            write_excel(original, output_path)

            # Parse the written file
            roundtripped = parse_excel(output_path)

            # Compare
            assert roundtripped.package == original.package
            assert len(roundtripped.rules) == len(original.rules)

            # Check that all rules have the expected structure
            for orig_rule, rt_rule in zip(original.rules, roundtripped.rules):
                assert len(rt_rule.fact_patterns) == len(orig_rule.fact_patterns)
                assert len(rt_rule.actions) == len(orig_rule.actions)

        finally:
            output_path.unlink()

    def test_roundtrip_fraud_rules(self, fixtures_dir):
        """Test roundtrip with more complex fraud rules."""
        original_path = fixtures_dir / "fraud_rules.xlsx"

        # Parse original
        original = parse_excel(original_path)

        # Write to new file
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            output_path = Path(f.name)

        try:
            write_excel(original, output_path)

            # Parse the written file
            roundtripped = parse_excel(output_path)

            # Compare basic structure
            assert roundtripped.package == original.package
            assert len(roundtripped.rules) == len(original.rules)

        finally:
            output_path.unlink()


class TestExcelWriterDRLRoundtrip:
    """Test roundtrip: Excel → IR → DRL → IR → Excel."""

    @pytest.fixture
    def fixtures_dir(self):
        return Path(__file__).parent / "fixtures"

    def test_full_roundtrip(self, fixtures_dir):
        """Excel → IR → DRL → IR → Excel should preserve semantics."""
        from drl_to_excel.drl_writer import write_drl
        from drl_to_excel.drl_parser import parse_drl_string

        original_path = fixtures_dir / "score_rules.xlsx"

        # Excel → IR
        ir1 = parse_excel(original_path)

        # IR → DRL
        drl = write_drl(ir1)

        # DRL → IR
        ir2 = parse_drl_string(drl, name=ir1.name)

        # IR → Excel
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            output_path = Path(f.name)

        try:
            write_excel(ir2, output_path)

            # Excel → IR (final)
            ir3 = parse_excel(output_path)

            # Compare original IR to final IR
            assert ir3.package == ir1.package
            assert len(ir3.rules) == len(ir1.rules)

        finally:
            output_path.unlink()


class TestExcelWriterConditions:
    """Test writing different condition types."""

    def test_writes_simple_conditions(self):
        ruleset = RuleSet(
            name="TestRules",
            package="com.example",
            rules=[
                Rule(
                    name="Rule1",
                    fact_patterns=[
                        FactPattern(
                            fact_type="Transaction",
                            binding="tx",
                            conditions=[
                                SimpleCondition(
                                    field="category",
                                    operator=Operator.EQ,
                                    value="ELECTRONICS"
                                )
                            ]
                        )
                    ],
                    actions=[
                        Action(
                            action_type=ActionType.SET_FIELD,
                            target="decision",
                            value="REVIEW",
                            binding="result"
                        )
                    ]
                )
            ]
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            output_path = Path(f.name)

        try:
            write_excel(ruleset, output_path)
            parsed = parse_excel(output_path)

            assert len(parsed.rules) == 1
            assert len(parsed.rules[0].fact_patterns) == 1

        finally:
            output_path.unlink()

    def test_writes_range_conditions(self):
        ruleset = RuleSet(
            name="TestRules",
            package="com.example",
            rules=[
                Rule(
                    name="Rule1",
                    fact_patterns=[
                        FactPattern(
                            fact_type="Transaction",
                            binding="tx",
                            conditions=[
                                RangeCondition(
                                    field="amount",
                                    min_value=100,
                                    max_value=500,
                                    min_inclusive=True,
                                    max_inclusive=False
                                )
                            ]
                        )
                    ],
                    actions=[
                        Action(
                            action_type=ActionType.SET_FIELD,
                            target="decision",
                            value="REVIEW",
                            binding="result"
                        )
                    ]
                )
            ]
        )

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            output_path = Path(f.name)

        try:
            write_excel(ruleset, output_path)
            parsed = parse_excel(output_path)

            assert len(parsed.rules) == 1
            # Find the range condition
            range_conds = [
                c for p in parsed.rules[0].fact_patterns
                for c in p.conditions
                if isinstance(c, RangeCondition)
            ]
            assert len(range_conds) == 1
            assert range_conds[0].min_value == 100
            assert range_conds[0].max_value == 500

        finally:
            output_path.unlink()
