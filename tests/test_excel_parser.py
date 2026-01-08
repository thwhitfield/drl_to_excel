"""Tests for Excel parser."""

import pytest
from pathlib import Path
from src.excel_parser import ExcelParser, parse_excel
from src.ir import Operator, ActionType, SimpleCondition, RangeCondition


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestExcelParserBasic:
    """Test basic parsing of score rules (simple conditions only)."""

    @pytest.fixture
    def score_ruleset(self):
        return parse_excel(FIXTURES_DIR / "score_rules.xlsx")

    def test_parses_package(self, score_ruleset):
        assert score_ruleset.package == "com.example.scoring"

    def test_parses_rule_table_name(self, score_ruleset):
        assert score_ruleset.rule_table_name == "ScoreRules"

    def test_parses_correct_number_of_rules(self, score_ruleset):
        assert len(score_ruleset.rules) == 4

    def test_parses_rule_names(self, score_ruleset):
        names = [r.name for r in score_ruleset.rules]
        assert names == [
            "ScoreRules_1",
            "ScoreRules_2",
            "ScoreRules_3",
            "ScoreRules_4",
        ]

    def test_parses_conditions(self, score_ruleset):
        rule = score_ruleset.rules[0]  # First rule: score >= 0.9 → DECLINE
        assert len(rule.fact_patterns) == 1

        pattern = rule.fact_patterns[0]
        assert pattern.fact_type == "Transaction"
        assert pattern.binding == "tx"
        assert len(pattern.conditions) == 1

        cond = pattern.conditions[0]
        assert isinstance(cond, SimpleCondition)
        assert cond.field == "score"
        assert cond.operator == Operator.GE
        assert cond.value == 0.9

    def test_parses_actions(self, score_ruleset):
        rule = score_ruleset.rules[0]  # First rule: score >= 0.9 → DECLINE
        assert len(rule.actions) == 1

        action = rule.actions[0]
        assert action.action_type == ActionType.SET_FIELD
        assert action.target == "decision"
        assert action.value == "DECLINE"
        assert action.binding == "result"


class TestExcelParserComplex:
    """Test parsing of fraud rules (includes range conditions)."""

    @pytest.fixture
    def fraud_ruleset(self):
        return parse_excel(FIXTURES_DIR / "fraud_rules.xlsx")

    def test_parses_imports(self, fraud_ruleset):
        assert "com.example.model.Transaction" in fraud_ruleset.imports
        assert "com.example.model.Result" in fraud_ruleset.imports

    def test_parses_rule_table_name(self, fraud_ruleset):
        assert fraud_ruleset.rule_table_name == "FraudRules"

    def test_parses_correct_number_of_rules(self, fraud_ruleset):
        # 5 data rows
        assert len(fraud_ruleset.rules) == 5

    def test_parses_range_condition(self, fraud_ruleset):
        # First rule has amount range: 1000 <= amount < 10000
        rule = fraud_ruleset.rules[0]

        # Find the range condition
        range_conds = [
            c for p in rule.fact_patterns
            for c in p.conditions
            if isinstance(c, RangeCondition)
        ]
        assert len(range_conds) == 1

        cond = range_conds[0]
        assert cond.field == "amount"
        assert cond.min_value == 1000
        assert cond.max_value == 10000

    def test_parses_category_condition(self, fraud_ruleset):
        # Fifth rule: category == "GAMBLING" → DECLINE
        rule = fraud_ruleset.rules[4]

        # Find category condition
        cat_conds = [
            c for p in rule.fact_patterns
            for c in p.conditions
            if isinstance(c, SimpleCondition) and c.field == "category"
        ]
        assert len(cat_conds) == 1
        assert cat_conds[0].value == "GAMBLING"

    def test_rule_with_multiple_conditions(self, fraud_ruleset):
        # First rule has: score > 0.8, amount range, category
        rule = fraud_ruleset.rules[0]

        all_conditions = [c for p in rule.fact_patterns for c in p.conditions]
        assert len(all_conditions) == 3  # score, amount range, category


class TestExcelParserDRLGeneration:
    """Test that parsed rules generate valid DRL."""

    def test_score_rules_to_drl(self):
        ruleset = parse_excel(FIXTURES_DIR / "score_rules.xlsx")
        drl = ruleset.to_drl()

        assert "package com.example.scoring;" in drl
        assert 'rule "ScoreRules_1"' in drl
        assert "$tx : Transaction(score >= 0.9)" in drl
        assert '$result.setDecision("DECLINE");' in drl

    def test_fraud_rules_to_drl(self):
        ruleset = parse_excel(FIXTURES_DIR / "fraud_rules.xlsx")
        drl = ruleset.to_drl()

        assert "package com.example.fraud;" in drl
        assert "import com.example.model.Transaction;" in drl
        assert 'rule "FraudRules_1"' in drl


class TestExcelParserEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_cells_are_skipped(self):
        # The fraud rules have empty cells - verify they don't cause issues
        ruleset = parse_excel(FIXTURES_DIR / "fraud_rules.xlsx")

        # Second rule only has score condition (other cells empty)
        rule = ruleset.rules[1]
        all_conditions = [c for p in rule.fact_patterns for c in p.conditions]
        assert len(all_conditions) == 1  # Only score

    def test_parser_reuse(self):
        """Test that parser can be reused for multiple files."""
        parser = ExcelParser()

        ruleset1 = parser.parse_file(FIXTURES_DIR / "score_rules.xlsx")
        ruleset2 = parser.parse_file(FIXTURES_DIR / "fraud_rules.xlsx")

        assert ruleset1.rule_table_name == "ScoreRules"
        assert ruleset2.rule_table_name == "FraudRules"
