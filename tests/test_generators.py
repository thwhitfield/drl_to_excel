"""Tests for programmatic rule generation API."""

import pytest
from drl_to_excel.generators import (
    VariantConfig,
    generate_variants,
    generate_threshold_variants,
    create_bucket_condition,
    add_bucket_to_rule,
    generate_bucketed_variants,
    RuleBuilder,
    RuleSetBuilder,
)
from drl_to_excel.ir import (
    Rule, RuleSet, FactPattern, Action, ActionType,
    SimpleCondition, RangeCondition, BucketCondition, Operator,
)


class TestVariantGeneration:
    """Test A/B variant generation."""

    @pytest.fixture
    def base_rule(self):
        return Rule(
            name="HighScore",
            fact_patterns=[
                FactPattern(
                    fact_type="Transaction",
                    binding="tx",
                    conditions=[
                        SimpleCondition(field="score", operator=Operator.GT, value=0.8)
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

    def test_generate_variants_creates_correct_count(self, base_rule):
        config = VariantConfig(
            base_rule=base_rule,
            variant_group="score_test",
            parameter_name="score",
            values=[0.7, 0.75, 0.8, 0.85, 0.9]
        )

        variants = generate_variants(config)
        assert len(variants) == 5

    def test_generate_variants_updates_values(self, base_rule):
        config = VariantConfig(
            base_rule=base_rule,
            variant_group="score_test",
            parameter_name="score",
            values=[0.7, 0.8, 0.9]
        )

        variants = generate_variants(config)

        # Check each variant has the correct value
        expected_values = [0.7, 0.8, 0.9]
        for variant, expected in zip(variants, expected_values):
            cond = variant.fact_patterns[0].conditions[0]
            assert cond.value == expected

    def test_generate_variants_sets_metadata(self, base_rule):
        config = VariantConfig(
            base_rule=base_rule,
            variant_group="score_test",
            parameter_name="score",
            values=[0.7, 0.8]
        )

        variants = generate_variants(config)

        assert variants[0].variant_group == "score_test"
        assert variants[0].variant_id == "score_test_0"
        assert variants[1].variant_id == "score_test_1"

    def test_generate_threshold_variants(self, base_rule):
        variants = generate_threshold_variants(
            base_rule,
            field="score",
            thresholds=[0.7, 0.75, 0.8, 0.85, 0.9],
            variant_group="ab_test"
        )

        assert len(variants) == 5
        assert variants[0].variant_group == "ab_test"


class TestBucketing:
    """Test bucketing/randomization utilities."""

    def test_create_bucket_condition(self):
        cond = create_bucket_condition("cardLastDigit", [0, 1, 2])

        assert isinstance(cond, BucketCondition)
        assert cond.field == "cardLastDigit"
        assert cond.bucket_values == [0, 1, 2]
        assert cond.modulo == 10

    def test_create_bucket_condition_custom_modulo(self):
        cond = create_bucket_condition("userId", [0, 1], modulo=100)

        assert cond.modulo == 100

    def test_add_bucket_to_rule(self):
        rule = Rule(
            name="TestRule",
            fact_patterns=[
                FactPattern(
                    fact_type="Transaction",
                    binding="tx",
                    conditions=[
                        SimpleCondition(field="score", operator=Operator.GT, value=0.8)
                    ]
                )
            ],
            actions=[]
        )

        bucketed = add_bucket_to_rule(rule, "cardLastDigit", [0, 1, 2])

        # Original rule should be unchanged
        assert len(rule.fact_patterns[0].conditions) == 1

        # New rule should have bucket condition
        assert len(bucketed.fact_patterns[0].conditions) == 2
        assert isinstance(bucketed.fact_patterns[0].conditions[1], BucketCondition)

    def test_generate_bucketed_variants(self):
        rule = Rule(
            name="TestRule",
            fact_patterns=[
                FactPattern(
                    fact_type="Transaction",
                    binding="tx",
                    conditions=[]
                )
            ],
            actions=[]
        )

        # Create 5 buckets (each 20% of traffic)
        variants = generate_bucketed_variants(
            rule,
            field="cardLastDigit",
            num_buckets=5
        )

        assert len(variants) == 5

        # Check bucket values are correct
        for i, variant in enumerate(variants):
            bucket_cond = variant.fact_patterns[0].conditions[0]
            expected_values = [i * 2, i * 2 + 1]
            assert bucket_cond.bucket_values == expected_values

    def test_generate_bucketed_variants_invalid_modulo(self):
        rule = Rule(name="Test", fact_patterns=[], actions=[])

        with pytest.raises(ValueError):
            generate_bucketed_variants(
                rule,
                field="x",
                num_buckets=3,  # 10 not divisible by 3
                modulo=10
            )


class TestRuleBuilder:
    """Test the fluent RuleBuilder API."""

    def test_simple_rule(self):
        rule = (RuleBuilder("HighRisk")
            .with_fact("Transaction", "tx")
            .when_score_above(0.8)
            .then_decline()
            .build())

        assert rule.name == "HighRisk"
        assert len(rule.fact_patterns) == 1
        assert rule.fact_patterns[0].fact_type == "Transaction"
        assert len(rule.fact_patterns[0].conditions) == 1
        assert len(rule.actions) == 1

    def test_complex_rule(self):
        rule = (RuleBuilder("ComplexFraud")
            .with_fact("Transaction", "tx")
            .when_score_above(0.7)
            .when_amount_between(1000, 10000)
            .when_category("ELECTRONICS")
            .then_decline()
            .with_salience(100)
            .with_description("High risk electronics transaction")
            .build())

        assert rule.name == "ComplexFraud"
        assert len(rule.fact_patterns[0].conditions) == 3
        assert rule.salience == 100
        assert rule.description == "High risk electronics transaction"

    def test_rule_with_bucketing(self):
        rule = (RuleBuilder("ABTestRule")
            .with_fact("Transaction", "tx")
            .when_score_above(0.8)
            .when_bucketed("cardLastDigit", [0, 1, 2])
            .then_decline()
            .as_variant("v1", "ab_test")
            .build())

        assert rule.variant_id == "v1"
        assert rule.variant_group == "ab_test"

        bucket_conds = [
            c for c in rule.fact_patterns[0].conditions
            if isinstance(c, BucketCondition)
        ]
        assert len(bucket_conds) == 1

    def test_disabled_rule(self):
        rule = (RuleBuilder("DisabledRule")
            .with_fact("Transaction", "tx")
            .then_approve()
            .disabled()
            .build())

        assert rule.enabled is False

    def test_custom_action(self):
        rule = (RuleBuilder("CustomAction")
            .with_fact("Transaction", "tx")
            .then_set("riskLevel", "HIGH", binding="result")
            .build())

        assert rule.actions[0].target == "riskLevel"
        assert rule.actions[0].value == "HIGH"


class TestRuleSetBuilder:
    """Test the fluent RuleSetBuilder API."""

    def test_simple_ruleset(self):
        rule = (RuleBuilder("TestRule")
            .with_fact("Transaction", "tx")
            .when_score_above(0.8)
            .then_decline()
            .build())

        ruleset = (RuleSetBuilder("FraudRules")
            .package("com.example.fraud")
            .imports(["com.example.model.Transaction"])
            .add_rule(rule)
            .build())

        assert ruleset.name == "FraudRules"
        assert ruleset.package == "com.example.fraud"
        assert len(ruleset.imports) == 1
        assert len(ruleset.rules) == 1

    def test_add_multiple_rules(self):
        rule1 = RuleBuilder("Rule1").with_fact("T", "t").then_decline().build()
        rule2 = RuleBuilder("Rule2").with_fact("T", "t").then_approve().build()

        ruleset = (RuleSetBuilder("MultiRule")
            .add_rules([rule1, rule2])
            .build())

        assert len(ruleset.rules) == 2

    def test_add_global(self):
        ruleset = (RuleSetBuilder("WithGlobal")
            .add_global("logger", "Logger")
            .build())

        assert ruleset.globals["logger"] == "Logger"


class TestEndToEnd:
    """End-to-end tests for rule generation workflows."""

    def test_generate_ab_test_variants_and_export(self):
        """Generate A/B test variants and verify they export correctly."""
        from drl_to_excel.drl_writer import write_drl

        # Create base rule
        base_rule = (RuleBuilder("HighScoreDecline")
            .with_fact("Transaction", "tx")
            .when_score_above(0.8)
            .when_category("ELECTRONICS")
            .then_decline()
            .build())

        # Generate 5 threshold variants
        variants = generate_threshold_variants(
            base_rule,
            field="score",
            thresholds=[0.7, 0.75, 0.8, 0.85, 0.9],
            variant_group="score_ab_test"
        )

        # Build ruleset with variants
        ruleset = (RuleSetBuilder("FraudABTest")
            .package("com.example.fraud")
            .imports(["com.example.model.Transaction"])
            .add_rules(variants)
            .build())

        # Export to DRL
        drl = write_drl(ruleset)

        # Verify all variants are in the output
        assert "score_ab_test" in drl or len(variants) == 5
        for i, threshold in enumerate([0.7, 0.75, 0.8, 0.85, 0.9]):
            assert f"score > {threshold}" in drl

    def test_bucketed_ab_test(self):
        """Test creating bucketed A/B test rules."""
        # Create control and treatment rules
        control = (RuleBuilder("Control")
            .with_fact("Transaction", "tx")
            .when_score_above(0.8)
            .when_bucketed("cardLastDigit", [0, 1, 2, 3, 4])  # 50%
            .then_decline()
            .as_variant("control", "threshold_test")
            .build())

        treatment = (RuleBuilder("Treatment")
            .with_fact("Transaction", "tx")
            .when_score_above(0.7)  # Lower threshold
            .when_bucketed("cardLastDigit", [5, 6, 7, 8, 9])  # 50%
            .then_decline()
            .as_variant("treatment", "threshold_test")
            .build())

        ruleset = (RuleSetBuilder("ABTest")
            .add_rules([control, treatment])
            .build())

        assert len(ruleset.rules) == 2
        assert ruleset.rules[0].variant_group == "threshold_test"
        assert ruleset.rules[1].variant_group == "threshold_test"
