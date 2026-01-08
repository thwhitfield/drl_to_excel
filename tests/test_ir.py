"""Tests for the Intermediate Representation module."""

import pytest
from src.ir import (
    Operator, ActionType,
    SimpleCondition, RangeCondition, BucketCondition, NullCheckCondition,
    FactPattern, Action, Rule, RuleSet,
    score_threshold, amount_range, category_check, decline_action,
)


class TestSimpleCondition:
    def test_numeric_comparison(self):
        cond = SimpleCondition(field="score", operator=Operator.GT, value=0.8)
        assert cond.to_drl_constraint() == "score > 0.8"

    def test_string_comparison(self):
        cond = SimpleCondition(field="category", operator=Operator.EQ, value="ELECTRONICS")
        assert cond.to_drl_constraint() == 'category == "ELECTRONICS"'

    def test_in_operator(self):
        cond = SimpleCondition(field="status", operator=Operator.IN, value=["PENDING", "REVIEW"])
        assert cond.to_drl_constraint() == 'status in ("PENDING", "REVIEW")'

    def test_matches_operator(self):
        cond = SimpleCondition(field="name", operator=Operator.MATCHES, value="^John.*")
        assert cond.to_drl_constraint() == 'name matches "^John.*"'


class TestRangeCondition:
    def test_full_range(self):
        cond = RangeCondition(field="amount", min_value=100, max_value=500)
        assert cond.to_drl_constraint() == "amount >= 100, amount < 500"

    def test_min_only(self):
        cond = RangeCondition(field="amount", min_value=100)
        assert cond.to_drl_constraint() == "amount >= 100"

    def test_max_only(self):
        cond = RangeCondition(field="amount", max_value=500)
        assert cond.to_drl_constraint() == "amount < 500"

    def test_inclusive_max(self):
        cond = RangeCondition(field="amount", min_value=100, max_value=500, max_inclusive=True)
        assert cond.to_drl_constraint() == "amount >= 100, amount <= 500"


class TestBucketCondition:
    def test_single_bucket(self):
        cond = BucketCondition(field="card_last_digit", bucket_values=[0])
        assert cond.to_drl_constraint() == "(card_last_digit % 10) == 0"

    def test_multiple_buckets(self):
        cond = BucketCondition(field="card_last_digit", bucket_values=[0, 1, 2])
        assert cond.to_drl_constraint() == "(card_last_digit % 10) in (0, 1, 2)"


class TestFactPattern:
    def test_with_binding_and_conditions(self):
        pattern = FactPattern(
            fact_type="Transaction",
            binding="tx",
            conditions=[
                SimpleCondition(field="amount", operator=Operator.GT, value=100),
                SimpleCondition(field="category", operator=Operator.EQ, value="ELECTRONICS"),
            ]
        )
        assert pattern.to_drl() == '$tx : Transaction(amount > 100, category == "ELECTRONICS")'

    def test_without_binding(self):
        pattern = FactPattern(
            fact_type="Transaction",
            conditions=[SimpleCondition(field="amount", operator=Operator.GT, value=100)]
        )
        assert pattern.to_drl() == "Transaction(amount > 100)"


class TestAction:
    def test_set_field_with_binding(self):
        action = Action(
            action_type=ActionType.SET_FIELD,
            target="decision",
            value="DECLINE",
            binding="result"
        )
        assert action.to_drl() == '$result.setDecision("DECLINE");'

    def test_insert_fact(self):
        action = Action(
            action_type=ActionType.INSERT_FACT,
            target="Alert",
            value="HIGH_RISK"
        )
        assert action.to_drl() == 'insert(new Alert("HIGH_RISK"));'


class TestRule:
    def test_simple_rule_to_drl(self):
        rule = Rule(
            name="High Score Decline",
            fact_patterns=[
                FactPattern(
                    fact_type="Transaction",
                    binding="tx",
                    conditions=[SimpleCondition(field="score", operator=Operator.GT, value=0.8)]
                )
            ],
            actions=[
                Action(
                    action_type=ActionType.SET_FIELD,
                    target="decision",
                    value="DECLINE",
                    binding="result"
                )
            ],
            salience=100
        )

        drl = rule.to_drl()
        assert 'rule "High Score Decline"' in drl
        assert "salience 100" in drl
        assert "$tx : Transaction(score > 0.8)" in drl
        assert '$result.setDecision("DECLINE");' in drl


class TestRuleSet:
    def test_full_ruleset_to_drl(self):
        ruleset = RuleSet(
            name="Fraud Rules",
            package="com.example.fraud",
            imports=["com.example.model.Transaction"],
            rules=[
                Rule(
                    name="High Score Decline",
                    fact_patterns=[
                        FactPattern(
                            fact_type="Transaction",
                            binding="tx",
                            conditions=[SimpleCondition(field="score", operator=Operator.GT, value=0.8)]
                        )
                    ],
                    actions=[decline_action()]
                )
            ]
        )

        drl = ruleset.to_drl()
        assert "package com.example.fraud;" in drl
        assert "import com.example.model.Transaction;" in drl
        assert 'rule "High Score Decline"' in drl


class TestHelperFactories:
    def test_score_threshold(self):
        cond = score_threshold(">", 0.8)
        assert cond.field == "score"
        assert cond.operator == Operator.GT
        assert cond.value == 0.8

    def test_amount_range(self):
        cond = amount_range(100, 500)
        assert cond.field == "amount"
        assert cond.min_value == 100
        assert cond.max_value == 500

    def test_category_check(self):
        cond = category_check("ELECTRONICS")
        assert cond.field == "category"
        assert cond.value == "ELECTRONICS"
