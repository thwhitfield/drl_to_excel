"""Tests for DRL parser."""

import pytest
from pathlib import Path
from drl_to_excel.drl_parser import DRLParser, parse_drl, parse_drl_string
from drl_to_excel.ir import Operator, ActionType, SimpleCondition, RangeCondition


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestDRLParserBasic:
    """Test basic DRL parsing."""

    def test_parses_package(self):
        drl = """
        package com.example.fraud;

        rule "Test"
        when
        then
        end
        """
        ruleset = parse_drl_string(drl)
        assert ruleset.package == "com.example.fraud"

    def test_parses_imports(self):
        drl = """
        package com.example;
        import com.example.model.Transaction;
        import com.example.model.Result;

        rule "Test"
        when
        then
        end
        """
        ruleset = parse_drl_string(drl)
        assert "com.example.model.Transaction" in ruleset.imports
        assert "com.example.model.Result" in ruleset.imports

    def test_parses_globals(self):
        drl = """
        package com.example;
        global Logger logger;
        global Integer counter;

        rule "Test"
        when
        then
        end
        """
        ruleset = parse_drl_string(drl)
        assert ruleset.globals["logger"] == "Logger"
        assert ruleset.globals["counter"] == "Integer"

    def test_parses_rule_name(self):
        drl = """
        package com.example;

        rule "My Test Rule"
        when
        then
        end
        """
        ruleset = parse_drl_string(drl)
        assert len(ruleset.rules) == 1
        assert ruleset.rules[0].name == "My Test Rule"

    def test_parses_multiple_rules(self):
        drl = """
        package com.example;

        rule "Rule One"
        when
        then
        end

        rule "Rule Two"
        when
        then
        end
        """
        ruleset = parse_drl_string(drl)
        assert len(ruleset.rules) == 2
        assert ruleset.rules[0].name == "Rule One"
        assert ruleset.rules[1].name == "Rule Two"


class TestDRLParserAttributes:
    """Test parsing of rule attributes."""

    def test_parses_salience(self):
        drl = """
        package com.example;

        rule "High Priority"
            salience 100
        when
        then
        end
        """
        ruleset = parse_drl_string(drl)
        assert ruleset.rules[0].salience == 100

    def test_parses_negative_salience(self):
        drl = """
        package com.example;

        rule "Low Priority"
            salience -50
        when
        then
        end
        """
        ruleset = parse_drl_string(drl)
        assert ruleset.rules[0].salience == -50

    def test_parses_enabled_false(self):
        drl = """
        package com.example;

        rule "Disabled Rule"
            enabled false
        when
        then
        end
        """
        ruleset = parse_drl_string(drl)
        assert ruleset.rules[0].enabled is False

    def test_parses_enabled_true(self):
        drl = """
        package com.example;

        rule "Enabled Rule"
            enabled true
        when
        then
        end
        """
        ruleset = parse_drl_string(drl)
        assert ruleset.rules[0].enabled is True


class TestDRLParserConditions:
    """Test parsing of when block conditions."""

    def test_parses_simple_fact_pattern(self):
        drl = """
        package com.example;

        rule "Test"
        when
            $tx : Transaction()
        then
        end
        """
        ruleset = parse_drl_string(drl)
        assert len(ruleset.rules[0].fact_patterns) == 1
        pattern = ruleset.rules[0].fact_patterns[0]
        assert pattern.binding == "tx"
        assert pattern.fact_type == "Transaction"

    def test_parses_numeric_comparison(self):
        drl = """
        package com.example;

        rule "Test"
        when
            $tx : Transaction(score > 0.8)
        then
        end
        """
        ruleset = parse_drl_string(drl)
        pattern = ruleset.rules[0].fact_patterns[0]
        assert len(pattern.conditions) == 1

        cond = pattern.conditions[0]
        assert isinstance(cond, SimpleCondition)
        assert cond.field == "score"
        assert cond.operator == Operator.GT
        assert cond.value == 0.8

    def test_parses_string_comparison(self):
        drl = """
        package com.example;

        rule "Test"
        when
            $tx : Transaction(category == "ELECTRONICS")
        then
        end
        """
        ruleset = parse_drl_string(drl)
        pattern = ruleset.rules[0].fact_patterns[0]
        cond = pattern.conditions[0]

        assert cond.field == "category"
        assert cond.operator == Operator.EQ
        assert cond.value == "ELECTRONICS"

    def test_parses_range_condition(self):
        drl = """
        package com.example;

        rule "Test"
        when
            $tx : Transaction(amount >= 100, amount < 500)
        then
        end
        """
        ruleset = parse_drl_string(drl)
        pattern = ruleset.rules[0].fact_patterns[0]

        # Should be parsed as a single RangeCondition
        range_conds = [c for c in pattern.conditions if isinstance(c, RangeCondition)]
        assert len(range_conds) == 1

        cond = range_conds[0]
        assert cond.field == "amount"
        assert cond.min_value == 100
        assert cond.max_value == 500
        assert cond.min_inclusive is True
        assert cond.max_inclusive is False

    def test_parses_multiple_conditions(self):
        drl = """
        package com.example;

        rule "Test"
        when
            $tx : Transaction(score > 0.8, category == "ELECTRONICS")
        then
        end
        """
        ruleset = parse_drl_string(drl)
        pattern = ruleset.rules[0].fact_patterns[0]

        assert len(pattern.conditions) == 2

    def test_parses_boolean_condition(self):
        drl = """
        package com.example;

        rule "Test"
        when
            $tx : Transaction(isInternational == true)
        then
        end
        """
        ruleset = parse_drl_string(drl)
        pattern = ruleset.rules[0].fact_patterns[0]
        cond = pattern.conditions[0]

        assert cond.field == "isInternational"
        assert cond.value is True


class TestDRLParserActions:
    """Test parsing of then block actions."""

    def test_parses_set_field_action(self):
        drl = """
        package com.example;

        rule "Test"
        when
            $tx : Transaction()
        then
            $result.setDecision("DECLINE");
        end
        """
        ruleset = parse_drl_string(drl)
        actions = ruleset.rules[0].actions

        assert len(actions) == 1
        action = actions[0]
        assert action.action_type == ActionType.SET_FIELD
        assert action.target == "decision"
        assert action.value == "DECLINE"
        assert action.binding == "result"

    def test_parses_insert_action(self):
        drl = """
        package com.example;

        rule "Test"
        when
            $tx : Transaction()
        then
            insert(new Alert("HIGH_RISK"));
        end
        """
        ruleset = parse_drl_string(drl)
        actions = ruleset.rules[0].actions

        assert len(actions) == 1
        action = actions[0]
        assert action.action_type == ActionType.INSERT_FACT
        assert action.target == "Alert"
        assert action.value == "HIGH_RISK"

    def test_parses_retract_action(self):
        drl = """
        package com.example;

        rule "Test"
        when
            $tx : Transaction()
        then
            retract($tx);
        end
        """
        ruleset = parse_drl_string(drl)
        actions = ruleset.rules[0].actions

        assert len(actions) == 1
        action = actions[0]
        assert action.action_type == ActionType.RETRACT_FACT
        assert action.binding == "tx"

    def test_parses_update_action(self):
        drl = """
        package com.example;

        rule "Test"
        when
            $tx : Transaction()
        then
            update($tx);
        end
        """
        ruleset = parse_drl_string(drl)
        actions = ruleset.rules[0].actions

        assert len(actions) == 1
        action = actions[0]
        assert action.action_type == ActionType.UPDATE_FACT
        assert action.binding == "tx"


class TestDRLParserComments:
    """Test that comments are properly handled."""

    def test_ignores_single_line_comments(self):
        drl = """
        package com.example;
        // This is a comment

        rule "Test"
        when
            // Another comment
            $tx : Transaction()
        then
        end
        """
        ruleset = parse_drl_string(drl)
        assert len(ruleset.rules) == 1

    def test_ignores_multi_line_comments(self):
        drl = """
        package com.example;
        /* This is a
           multi-line comment */

        rule "Test"
        when
            $tx : Transaction()
        then
        end
        """
        ruleset = parse_drl_string(drl)
        assert len(ruleset.rules) == 1


class TestDRLParserRoundtrip:
    """Test that parsed DRL can be regenerated."""

    def test_parse_and_regenerate(self):
        drl = """
        package com.example.fraud;

        import com.example.model.Transaction;

        rule "HighScoreDecline"
            salience 100
        when
            $tx : Transaction(score > 0.8)
        then
            $result.setDecision("DECLINE");
        end
        """
        ruleset = parse_drl_string(drl)
        regenerated = ruleset.to_drl()

        # Parse the regenerated DRL
        ruleset2 = parse_drl_string(regenerated)

        assert ruleset2.package == ruleset.package
        assert ruleset2.imports == ruleset.imports
        assert len(ruleset2.rules) == len(ruleset.rules)
        assert ruleset2.rules[0].name == ruleset.rules[0].name
        assert ruleset2.rules[0].salience == ruleset.rules[0].salience


class TestDRLParserFromFile:
    """Test parsing from actual DRL files."""

    def test_parse_generated_drl_file(self):
        # First, let's create the DRL file if it exists from examples
        drl_path = FIXTURES_DIR.parent.parent / "examples" / "output" / "fraud_rules.drl"

        if drl_path.exists():
            ruleset = parse_drl(drl_path)
            assert ruleset.package == "com.example.fraud"
            assert len(ruleset.rules) > 0
