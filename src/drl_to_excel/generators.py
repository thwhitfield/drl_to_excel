"""
Programmatic Rule Generation API.

Provides utilities for:
- Creating A/B test variants (sweeping parameters across multiple values)
- Bucketing rules for randomization (card number last digit, user ID modulo, etc.)
- Cloning and modifying existing rules
"""

from dataclasses import dataclass, field
from typing import Iterator, Callable
from copy import deepcopy

from drl_to_excel.ir import (
    Rule, RuleSet, FactPattern, Action, Condition,
    SimpleCondition, RangeCondition, BucketCondition,
    Operator, ActionType,
    score_threshold, amount_range, decline_action, approve_action, review_action,
)


# =============================================================================
# A/B Variant Generation
# =============================================================================

@dataclass
class VariantConfig:
    """Configuration for generating rule variants."""
    base_rule: Rule
    variant_group: str
    parameter_name: str  # Which field to vary (e.g., "score", "amount")
    values: list  # Values to sweep
    name_template: str = "{base_name}_variant_{index}"


def generate_variants(config: VariantConfig) -> list[Rule]:
    """
    Generate multiple rule variants by sweeping a parameter.

    Args:
        config: VariantConfig specifying how to generate variants

    Returns:
        List of Rule variants with updated conditions

    Example:
        >>> base_rule = Rule(name="HighScore", ...)
        >>> config = VariantConfig(
        ...     base_rule=base_rule,
        ...     variant_group="score_test",
        ...     parameter_name="score",
        ...     values=[0.7, 0.75, 0.8, 0.85, 0.9]
        ... )
        >>> variants = generate_variants(config)
    """
    variants = []

    for idx, value in enumerate(config.values):
        # Deep copy the base rule
        variant = deepcopy(config.base_rule)

        # Update name
        variant.name = config.name_template.format(
            base_name=config.base_rule.name,
            index=idx,
            value=value
        )

        # Update variant metadata
        variant.variant_id = f"{config.variant_group}_{idx}"
        variant.variant_group = config.variant_group

        # Update the condition with the new value
        _update_condition_value(variant, config.parameter_name, value)

        variants.append(variant)

    return variants


def generate_threshold_variants(
    base_rule: Rule,
    field: str,
    thresholds: list[float],
    variant_group: str | None = None,
) -> list[Rule]:
    """
    Convenience function to generate threshold variants for a field.

    Args:
        base_rule: The rule to use as template
        field: The field to vary (e.g., "score")
        thresholds: List of threshold values to generate
        variant_group: Optional group name for the variants

    Returns:
        List of Rule variants

    Example:
        >>> variants = generate_threshold_variants(
        ...     base_rule,
        ...     field="score",
        ...     thresholds=[0.7, 0.75, 0.8, 0.85, 0.9],
        ...     variant_group="score_ab_test"
        ... )
    """
    config = VariantConfig(
        base_rule=base_rule,
        variant_group=variant_group or f"{field}_variants",
        parameter_name=field,
        values=thresholds,
        name_template=f"{{base_name}}_{field}_{{value}}"
    )
    return generate_variants(config)


def _update_condition_value(rule: Rule, field: str, value) -> bool:
    """Update a condition's value by field name. Returns True if updated."""
    for pattern in rule.fact_patterns:
        for i, condition in enumerate(pattern.conditions):
            if condition.get_field_name() == field:
                if isinstance(condition, SimpleCondition):
                    pattern.conditions[i] = SimpleCondition(
                        field=condition.field,
                        operator=condition.operator,
                        value=value,
                    )
                    return True
                elif isinstance(condition, RangeCondition):
                    # For ranges, update the min value
                    pattern.conditions[i] = RangeCondition(
                        field=condition.field,
                        min_value=value,
                        max_value=condition.max_value,
                        min_inclusive=condition.min_inclusive,
                        max_inclusive=condition.max_inclusive,
                    )
                    return True
    return False


# =============================================================================
# Bucketing / Randomization
# =============================================================================

def create_bucket_condition(
    field: str,
    bucket_values: list[int],
    modulo: int = 10,
) -> BucketCondition:
    """
    Create a bucketing condition for A/B testing.

    Args:
        field: The field to bucket on (e.g., "cardNumberLastDigit", "userId")
        bucket_values: Which bucket values to match (e.g., [0, 1, 2] for 30%)
        modulo: The modulo to use (default 10 for last digit)

    Returns:
        BucketCondition

    Example:
        >>> # 30% of traffic (last digit 0, 1, or 2)
        >>> cond = create_bucket_condition("cardLastDigit", [0, 1, 2])
    """
    return BucketCondition(
        field=field,
        bucket_values=bucket_values,
        modulo=modulo,
    )


def add_bucket_to_rule(
    rule: Rule,
    field: str,
    bucket_values: list[int],
    modulo: int = 10,
    pattern_index: int = 0,
) -> Rule:
    """
    Add a bucketing condition to an existing rule.

    Args:
        rule: The rule to modify (will be deep copied)
        field: The field to bucket on
        bucket_values: Which bucket values to match
        modulo: The modulo to use
        pattern_index: Which fact pattern to add the condition to

    Returns:
        New Rule with bucketing condition added
    """
    new_rule = deepcopy(rule)

    bucket_cond = create_bucket_condition(field, bucket_values, modulo)

    if pattern_index < len(new_rule.fact_patterns):
        new_rule.fact_patterns[pattern_index].conditions.append(bucket_cond)

    return new_rule


def generate_bucketed_variants(
    rule: Rule,
    field: str,
    num_buckets: int,
    modulo: int = 10,
    variant_group: str | None = None,
) -> list[Rule]:
    """
    Generate rule variants for different traffic buckets.

    Args:
        rule: Base rule to create variants from
        field: Field to bucket on (e.g., "cardLastDigit")
        num_buckets: How many equal-sized buckets to create
        modulo: The modulo to use (should be divisible by num_buckets)
        variant_group: Optional group name

    Returns:
        List of rules, one per bucket

    Example:
        >>> # Create 5 variants, each getting 20% of traffic
        >>> variants = generate_bucketed_variants(
        ...     rule,
        ...     field="cardLastDigit",
        ...     num_buckets=5
        ... )
    """
    if modulo % num_buckets != 0:
        raise ValueError(f"modulo ({modulo}) must be divisible by num_buckets ({num_buckets})")

    bucket_size = modulo // num_buckets
    variants = []

    for bucket_idx in range(num_buckets):
        start = bucket_idx * bucket_size
        bucket_values = list(range(start, start + bucket_size))

        variant = add_bucket_to_rule(rule, field, bucket_values, modulo)
        variant.name = f"{rule.name}_bucket_{bucket_idx}"
        variant.variant_id = f"bucket_{bucket_idx}"
        variant.variant_group = variant_group or f"{rule.name}_buckets"

        variants.append(variant)

    return variants


# =============================================================================
# Rule Builder (Fluent API)
# =============================================================================

class RuleBuilder:
    """
    Fluent builder for creating rules programmatically.

    Example:
        >>> rule = (RuleBuilder("HighRiskTransaction")
        ...     .with_fact("Transaction", "tx")
        ...     .when_score_above(0.8)
        ...     .when_amount_between(1000, 10000)
        ...     .when_category("ELECTRONICS")
        ...     .then_decline()
        ...     .with_salience(100)
        ...     .build())
    """

    def __init__(self, name: str):
        self.name = name
        self.fact_patterns: list[FactPattern] = []
        self.actions: list[Action] = []
        self.salience: int | None = None
        self.enabled: bool = True
        self.description: str | None = None
        self.variant_id: str | None = None
        self.variant_group: str | None = None

        # Current fact pattern being built
        self._current_pattern: FactPattern | None = None

    def with_fact(self, fact_type: str, binding: str) -> "RuleBuilder":
        """Add a fact pattern to match."""
        self._current_pattern = FactPattern(
            fact_type=fact_type,
            binding=binding,
            conditions=[],
        )
        self.fact_patterns.append(self._current_pattern)
        return self

    def when(self, condition: Condition) -> "RuleBuilder":
        """Add a condition to the current fact pattern."""
        if self._current_pattern is None:
            raise ValueError("Must call with_fact() before adding conditions")
        self._current_pattern.conditions.append(condition)
        return self

    def when_score_above(self, threshold: float, field: str = "score") -> "RuleBuilder":
        """Add a score threshold condition (score > threshold)."""
        return self.when(score_threshold(">", threshold, field))

    def when_score_at_least(self, threshold: float, field: str = "score") -> "RuleBuilder":
        """Add a score threshold condition (score >= threshold)."""
        return self.when(score_threshold(">=", threshold, field))

    def when_amount_between(
        self,
        min_val: float,
        max_val: float,
        field: str = "amount"
    ) -> "RuleBuilder":
        """Add an amount range condition."""
        return self.when(amount_range(min_val, max_val, field))

    def when_amount_above(self, threshold: float, field: str = "amount") -> "RuleBuilder":
        """Add an amount minimum condition."""
        return self.when(amount_range(threshold, None, field))

    def when_category(self, category: str, field: str = "category") -> "RuleBuilder":
        """Add a category equality condition."""
        return self.when(SimpleCondition(field=field, operator=Operator.EQ, value=category))

    def when_field_equals(self, field: str, value) -> "RuleBuilder":
        """Add a field equality condition."""
        return self.when(SimpleCondition(field=field, operator=Operator.EQ, value=value))

    def when_field_in(self, field: str, values: list) -> "RuleBuilder":
        """Add a field IN condition."""
        return self.when(SimpleCondition(field=field, operator=Operator.IN, value=values))

    def when_bucketed(
        self,
        field: str,
        bucket_values: list[int],
        modulo: int = 10
    ) -> "RuleBuilder":
        """Add a bucketing condition for A/B testing."""
        return self.when(BucketCondition(field=field, bucket_values=bucket_values, modulo=modulo))

    def then(self, action: Action) -> "RuleBuilder":
        """Add an action."""
        self.actions.append(action)
        return self

    def then_decline(self, binding: str = "result") -> "RuleBuilder":
        """Add a DECLINE action."""
        return self.then(decline_action(binding))

    def then_approve(self, binding: str = "result") -> "RuleBuilder":
        """Add an APPROVE action."""
        return self.then(approve_action(binding))

    def then_review(self, binding: str = "result") -> "RuleBuilder":
        """Add a REVIEW action."""
        return self.then(review_action(binding))

    def then_set(self, field: str, value, binding: str = "result") -> "RuleBuilder":
        """Add a SET_FIELD action."""
        return self.then(Action(
            action_type=ActionType.SET_FIELD,
            target=field,
            value=value,
            binding=binding,
        ))

    def with_salience(self, salience: int) -> "RuleBuilder":
        """Set rule salience (priority)."""
        self.salience = salience
        return self

    def with_description(self, description: str) -> "RuleBuilder":
        """Set rule description."""
        self.description = description
        return self

    def as_variant(self, variant_id: str, variant_group: str) -> "RuleBuilder":
        """Mark this rule as a variant."""
        self.variant_id = variant_id
        self.variant_group = variant_group
        return self

    def disabled(self) -> "RuleBuilder":
        """Disable the rule."""
        self.enabled = False
        return self

    def build(self) -> Rule:
        """Build and return the Rule."""
        return Rule(
            name=self.name,
            fact_patterns=self.fact_patterns,
            actions=self.actions,
            salience=self.salience,
            enabled=self.enabled,
            description=self.description,
            variant_id=self.variant_id,
            variant_group=self.variant_group,
        )


# =============================================================================
# RuleSet Builder
# =============================================================================

class RuleSetBuilder:
    """
    Fluent builder for creating rule sets.

    Example:
        >>> ruleset = (RuleSetBuilder("FraudRules")
        ...     .package("com.example.fraud")
        ...     .imports(["com.example.model.Transaction"])
        ...     .add_rule(rule1)
        ...     .add_rule(rule2)
        ...     .build())
    """

    def __init__(self, name: str):
        self._name = name
        self._package = "com.example.rules"
        self._imports: list[str] = []
        self._rules: list[Rule] = []
        self._globals: dict[str, str] = {}

    def package(self, package: str) -> "RuleSetBuilder":
        """Set the package name."""
        self._package = package
        return self

    def imports(self, imports: list[str]) -> "RuleSetBuilder":
        """Set the imports."""
        self._imports = imports
        return self

    def add_import(self, import_str: str) -> "RuleSetBuilder":
        """Add a single import."""
        self._imports.append(import_str)
        return self

    def add_global(self, name: str, type_name: str) -> "RuleSetBuilder":
        """Add a global variable."""
        self._globals[name] = type_name
        return self

    def add_rule(self, rule: Rule) -> "RuleSetBuilder":
        """Add a rule."""
        self._rules.append(rule)
        return self

    def add_rules(self, rules: list[Rule]) -> "RuleSetBuilder":
        """Add multiple rules."""
        self._rules.extend(rules)
        return self

    def build(self) -> RuleSet:
        """Build and return the RuleSet."""
        return RuleSet(
            name=self._name,
            package=self._package,
            imports=self._imports,
            rules=self._rules,
            globals=self._globals,
        )
