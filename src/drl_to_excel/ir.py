"""
Intermediate Representation (IR) for Drools Decision Tables.

This module defines the core dataclasses that represent rules in a format-agnostic way,
enabling bidirectional conversion between Excel decision tables and DRL.

Architecture:
    Excel ←→ IR ←→ DRL
              ↑
       Programmatic generation
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from abc import ABC, abstractmethod


# =============================================================================
# Enums
# =============================================================================

class Operator(Enum):
    """Comparison operators for conditions."""
    EQ = "=="
    NE = "!="
    GT = ">"
    GE = ">="
    LT = "<"
    LE = "<="
    IN = "in"
    NOT_IN = "not in"
    MATCHES = "matches"
    CONTAINS = "contains"


class ActionType(Enum):
    """Types of actions a rule can perform."""
    SET_FIELD = "set_field"
    INSERT_FACT = "insert"
    RETRACT_FACT = "retract"
    UPDATE_FACT = "update"
    LOG = "log"
    CUSTOM = "custom"


# =============================================================================
# Conditions
# =============================================================================

@dataclass
class Condition(ABC):
    """Base class for all condition types."""

    @abstractmethod
    def to_drl_constraint(self) -> str:
        """Convert condition to DRL constraint syntax."""
        pass

    @abstractmethod
    def get_field_name(self) -> str:
        """Return the field name this condition applies to."""
        pass


@dataclass
class SimpleCondition(Condition):
    """A simple field comparison condition.

    Examples:
        - score > 0.8
        - amount >= 100
        - category == "ELECTRONICS"
    """
    field: str
    operator: Operator
    value: Any

    def to_drl_constraint(self) -> str:
        if self.operator == Operator.IN:
            return f"{self.field} in ({self._format_value(self.value)})"
        elif self.operator == Operator.NOT_IN:
            return f"{self.field} not in ({self._format_value(self.value)})"
        elif self.operator == Operator.MATCHES:
            return f'{self.field} matches "{self.value}"'
        elif self.operator == Operator.CONTAINS:
            return f'{self.field} contains "{self.value}"'
        else:
            return f"{self.field} {self.operator.value} {self._format_value(self.value)}"

    def _format_value(self, value: Any) -> str:
        if isinstance(value, str):
            return f'"{value}"'
        elif isinstance(value, bool):
            return str(value).lower()
        elif isinstance(value, (list, tuple)):
            return ", ".join(self._format_value(v) for v in value)
        else:
            return str(value)

    def get_field_name(self) -> str:
        return self.field


@dataclass
class RangeCondition(Condition):
    """A range condition for numeric fields.

    Examples:
        - 100 <= amount < 500
        - 0.5 <= score <= 0.8
    """
    field: str
    min_value: float | int | None = None
    max_value: float | int | None = None
    min_inclusive: bool = True
    max_inclusive: bool = False

    def to_drl_constraint(self) -> str:
        constraints = []
        if self.min_value is not None:
            op = ">=" if self.min_inclusive else ">"
            constraints.append(f"{self.field} {op} {self.min_value}")
        if self.max_value is not None:
            op = "<=" if self.max_inclusive else "<"
            constraints.append(f"{self.field} {op} {self.max_value}")
        return ", ".join(constraints)

    def get_field_name(self) -> str:
        return self.field


@dataclass
class BucketCondition(Condition):
    """A bucketing condition for A/B testing.

    Examples:
        - card_number_last_digit in (0, 1, 2)  // 30% bucket
        - user_id % 10 < 5  // 50% bucket
    """
    field: str
    bucket_values: list[int]
    modulo: int = 10

    def to_drl_constraint(self) -> str:
        if len(self.bucket_values) == 1:
            return f"({self.field} % {self.modulo}) == {self.bucket_values[0]}"
        else:
            values = ", ".join(str(v) for v in self.bucket_values)
            return f"({self.field} % {self.modulo}) in ({values})"

    def get_field_name(self) -> str:
        return self.field


@dataclass
class NullCheckCondition(Condition):
    """Check if a field is null or not null."""
    field: str
    is_null: bool = True

    def to_drl_constraint(self) -> str:
        if self.is_null:
            return f"{self.field} == null"
        else:
            return f"{self.field} != null"

    def get_field_name(self) -> str:
        return self.field


# =============================================================================
# Fact Patterns
# =============================================================================

@dataclass
class FactPattern:
    """A fact pattern that binds a variable to a fact type with conditions.

    In DRL:
        $transaction : Transaction(amount > 100, category == "ELECTRONICS")
    """
    fact_type: str
    binding: str | None = None
    conditions: list[Condition] = field(default_factory=list)

    def to_drl(self) -> str:
        constraints = ", ".join(c.to_drl_constraint() for c in self.conditions)
        binding_prefix = f"${self.binding} : " if self.binding else ""
        return f"{binding_prefix}{self.fact_type}({constraints})"


# =============================================================================
# Actions
# =============================================================================

@dataclass
class Action:
    """An action performed when a rule fires.

    Examples:
        - Set result to DECLINE
        - Insert a new Alert fact
        - Log a message
    """
    action_type: ActionType
    target: str  # Field name, fact type, or log message
    value: Any = None
    binding: str | None = None  # For fact operations, the variable to operate on

    def to_drl(self) -> str:
        if self.action_type == ActionType.SET_FIELD:
            formatted_value = self._format_value(self.value)
            if self.binding:
                return f"${self.binding}.set{self.target.capitalize()}({formatted_value});"
            else:
                return f"{self.target} = {formatted_value};"
        elif self.action_type == ActionType.INSERT_FACT:
            return f"insert(new {self.target}({self._format_value(self.value)}));"
        elif self.action_type == ActionType.RETRACT_FACT:
            return f"retract(${self.binding});"
        elif self.action_type == ActionType.UPDATE_FACT:
            return f"update(${self.binding});"
        elif self.action_type == ActionType.LOG:
            return f'System.out.println("{self.target}");'
        else:
            return str(self.value)

    def _format_value(self, value: Any) -> str:
        if isinstance(value, str):
            return f'"{value}"'
        elif isinstance(value, bool):
            return str(value).lower()
        elif value is None:
            return "null"
        else:
            return str(value)


# =============================================================================
# Rules
# =============================================================================

@dataclass
class Rule:
    """A single rule with conditions and actions.

    This is the core unit of the IR, representing one row in a decision table
    or one rule block in DRL.
    """
    name: str
    fact_patterns: list[FactPattern] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    salience: int | None = None
    enabled: bool = True
    description: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    # For A/B testing support
    variant_id: str | None = None
    variant_group: str | None = None

    def to_drl(self) -> str:
        lines = []

        # Rule declaration
        lines.append(f'rule "{self.name}"')

        # Attributes
        if self.salience is not None:
            lines.append(f"    salience {self.salience}")
        if not self.enabled:
            lines.append("    enabled false")

        # When clause
        lines.append("    when")
        for pattern in self.fact_patterns:
            lines.append(f"        {pattern.to_drl()}")

        # Then clause
        lines.append("    then")
        for action in self.actions:
            lines.append(f"        {action.to_drl()}")

        lines.append("end")

        return "\n".join(lines)


# =============================================================================
# RuleSet (Top-level container)
# =============================================================================

@dataclass
class RuleSet:
    """A collection of rules with shared metadata.

    This represents an entire decision table or DRL file.
    """
    name: str
    package: str = "com.example.rules"
    imports: list[str] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)
    globals: dict[str, str] = field(default_factory=dict)  # name -> type

    # Metadata for Excel format
    rule_table_name: str | None = None
    fact_type: str | None = None  # Primary fact type for decision table

    def to_drl(self) -> str:
        lines = []

        # Package
        lines.append(f"package {self.package};")
        lines.append("")

        # Imports
        for imp in self.imports:
            lines.append(f"import {imp};")
        if self.imports:
            lines.append("")

        # Globals
        for name, type_name in self.globals.items():
            lines.append(f"global {type_name} {name};")
        if self.globals:
            lines.append("")

        # Rules
        for rule in self.rules:
            if rule.enabled:
                lines.append(rule.to_drl())
                lines.append("")

        return "\n".join(lines)

    def add_rule(self, rule: Rule) -> None:
        """Add a rule to the ruleset."""
        self.rules.append(rule)

    def get_rules_by_variant_group(self, group: str) -> list[Rule]:
        """Get all rules belonging to a variant group."""
        return [r for r in self.rules if r.variant_group == group]


# =============================================================================
# Helper Factory Functions (for ergonomic rule creation)
# =============================================================================

def score_threshold(operator: str, value: float, field: str = "score") -> SimpleCondition:
    """Create a score threshold condition.

    Example:
        score_threshold(">", 0.8) -> score > 0.8
    """
    op_map = {
        "==": Operator.EQ, "!=": Operator.NE,
        ">": Operator.GT, ">=": Operator.GE,
        "<": Operator.LT, "<=": Operator.LE,
    }
    return SimpleCondition(field=field, operator=op_map[operator], value=value)


def amount_range(
    min_val: float | None = None,
    max_val: float | None = None,
    field: str = "amount"
) -> RangeCondition:
    """Create an amount range condition.

    Example:
        amount_range(100, 500) -> amount >= 100, amount < 500
    """
    return RangeCondition(field=field, min_value=min_val, max_value=max_val)


def category_check(category: str, field: str = "category") -> SimpleCondition:
    """Create a category equality condition.

    Example:
        category_check("ELECTRONICS") -> category == "ELECTRONICS"
    """
    return SimpleCondition(field=field, operator=Operator.EQ, value=category)


def decline_action(binding: str = "result") -> Action:
    """Create a DECLINE action."""
    return Action(
        action_type=ActionType.SET_FIELD,
        target="decision",
        value="DECLINE",
        binding=binding
    )


def approve_action(binding: str = "result") -> Action:
    """Create an APPROVE action."""
    return Action(
        action_type=ActionType.SET_FIELD,
        target="decision",
        value="APPROVE",
        binding=binding
    )


def review_action(binding: str = "result") -> Action:
    """Create a REVIEW action."""
    return Action(
        action_type=ActionType.SET_FIELD,
        target="decision",
        value="REVIEW",
        binding=binding
    )
