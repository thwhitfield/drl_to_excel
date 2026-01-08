"""
DRL Parser.

Parses Drools Rule Language (DRL) files into IR.

This is a constrained parser designed for simple rule patterns commonly used
in fraud detection and decision tables:
- Simple field comparisons (score > 0.8)
- Range conditions (amount >= 100, amount < 500)
- Category checks (category == "ELECTRONICS")
- Basic actions (setting fields, inserting facts)

It does NOT support the full DRL syntax (no functions, no complex expressions,
no accumulate, etc.).
"""

import re
from pathlib import Path
from dataclasses import dataclass

from drl_to_excel.ir import (
    Operator, ActionType,
    SimpleCondition, RangeCondition, Condition,
    FactPattern, Action, Rule, RuleSet,
)


class DRLParserError(Exception):
    """Raised when DRL parsing fails."""
    pass


@dataclass
class TokenizedRule:
    """Intermediate representation of a parsed rule before full IR conversion."""
    name: str
    attributes: dict[str, str]
    when_block: str
    then_block: str


class DRLParser:
    """Parser for DRL files into IR."""

    # Regex patterns
    PACKAGE_PATTERN = re.compile(r"package\s+([\w.]+)\s*;")
    IMPORT_PATTERN = re.compile(r"import\s+([\w.]+)\s*;")
    GLOBAL_PATTERN = re.compile(r"global\s+(\w+)\s+(\w+)\s*;")

    # Rule pattern - captures rule name and body
    RULE_PATTERN = re.compile(
        r'rule\s+"([^"]+)"\s*(.*?)\s*when\s*(.*?)\s*then\s*(.*?)\s*end',
        re.DOTALL
    )

    # Attribute patterns
    SALIENCE_PATTERN = re.compile(r"salience\s+(-?\d+)")
    ENABLED_PATTERN = re.compile(r"enabled\s+(true|false)")

    # Fact pattern: $binding : FactType(constraints)
    FACT_PATTERN = re.compile(
        r"\$(\w+)\s*:\s*(\w+)\s*\(([^)]*)\)"
    )

    # Constraint patterns
    SIMPLE_CONSTRAINT = re.compile(
        r"(\w+)\s*(==|!=|>=|<=|>|<|in|not in|matches|contains)\s*(.+)"
    )

    # Action patterns
    SET_FIELD_PATTERN = re.compile(
        r"\$(\w+)\.set(\w+)\s*\(\s*(.+?)\s*\)\s*;"
    )
    INSERT_PATTERN = re.compile(
        r"insert\s*\(\s*new\s+(\w+)\s*\(\s*(.+?)\s*\)\s*\)\s*;"
    )
    RETRACT_PATTERN = re.compile(
        r"retract\s*\(\s*\$(\w+)\s*\)\s*;"
    )
    UPDATE_PATTERN = re.compile(
        r"update\s*\(\s*\$(\w+)\s*\)\s*;"
    )

    # Operator mapping
    OPERATOR_MAP = {
        "==": Operator.EQ,
        "!=": Operator.NE,
        ">": Operator.GT,
        ">=": Operator.GE,
        "<": Operator.LT,
        "<=": Operator.LE,
        "in": Operator.IN,
        "not in": Operator.NOT_IN,
        "matches": Operator.MATCHES,
        "contains": Operator.CONTAINS,
    }

    def __init__(self):
        self.package: str = ""
        self.imports: list[str] = []
        self.globals: dict[str, str] = {}

    def parse_file(self, file_path: str | Path) -> RuleSet:
        """Parse a DRL file into IR."""
        path = Path(file_path)
        content = path.read_text()
        return self.parse_string(content, name=path.stem)

    def parse_string(self, content: str, name: str = "ParsedRules") -> RuleSet:
        """Parse DRL content string into IR."""
        self._reset()

        # Remove comments
        content = self._remove_comments(content)

        # Parse package
        self._parse_package(content)

        # Parse imports
        self._parse_imports(content)

        # Parse globals
        self._parse_globals(content)

        # Parse rules
        rules = self._parse_rules(content)

        return RuleSet(
            name=name,
            package=self.package,
            imports=self.imports,
            globals=self.globals,
            rules=rules,
        )

    def _reset(self):
        """Reset parser state."""
        self.package = ""
        self.imports = []
        self.globals = {}

    def _remove_comments(self, content: str) -> str:
        """Remove single-line and multi-line comments."""
        # Remove single-line comments
        content = re.sub(r"//.*$", "", content, flags=re.MULTILINE)
        # Remove multi-line comments
        content = re.sub(r"/\*.*?\*/", "", content, flags=re.DOTALL)
        return content

    def _parse_package(self, content: str):
        """Extract package declaration."""
        match = self.PACKAGE_PATTERN.search(content)
        if match:
            self.package = match.group(1)

    def _parse_imports(self, content: str):
        """Extract import statements."""
        for match in self.IMPORT_PATTERN.finditer(content):
            self.imports.append(match.group(1))

    def _parse_globals(self, content: str):
        """Extract global declarations."""
        for match in self.GLOBAL_PATTERN.finditer(content):
            type_name = match.group(1)
            var_name = match.group(2)
            self.globals[var_name] = type_name

    def _parse_rules(self, content: str) -> list[Rule]:
        """Parse all rules from content."""
        rules = []

        for match in self.RULE_PATTERN.finditer(content):
            rule_name = match.group(1)
            attributes_block = match.group(2)
            when_block = match.group(3)
            then_block = match.group(4)

            rule = self._parse_rule(
                rule_name,
                attributes_block,
                when_block,
                then_block
            )
            rules.append(rule)

        return rules

    def _parse_rule(
        self,
        name: str,
        attributes_block: str,
        when_block: str,
        then_block: str
    ) -> Rule:
        """Parse a single rule into IR."""
        # Parse attributes
        salience = None
        enabled = True

        salience_match = self.SALIENCE_PATTERN.search(attributes_block)
        if salience_match:
            salience = int(salience_match.group(1))

        enabled_match = self.ENABLED_PATTERN.search(attributes_block)
        if enabled_match:
            enabled = enabled_match.group(1).lower() == "true"

        # Parse fact patterns from when block
        fact_patterns = self._parse_when_block(when_block)

        # Parse actions from then block
        actions = self._parse_then_block(then_block)

        return Rule(
            name=name,
            fact_patterns=fact_patterns,
            actions=actions,
            salience=salience,
            enabled=enabled,
        )

    def _parse_when_block(self, when_block: str) -> list[FactPattern]:
        """Parse the when block into fact patterns."""
        fact_patterns = []

        for match in self.FACT_PATTERN.finditer(when_block):
            binding = match.group(1)
            fact_type = match.group(2)
            constraints_str = match.group(3)

            conditions = self._parse_constraints(constraints_str)

            fact_patterns.append(FactPattern(
                fact_type=fact_type,
                binding=binding,
                conditions=conditions,
            ))

        return fact_patterns

    def _parse_constraints(self, constraints_str: str) -> list[Condition]:
        """Parse constraint string into conditions."""
        conditions = []

        if not constraints_str.strip():
            return conditions

        # Split by comma, but be careful of commas inside strings/parentheses
        constraint_parts = self._split_constraints(constraints_str)

        # Group constraints by field to detect range conditions
        field_constraints: dict[str, list[tuple[str, str]]] = {}

        for part in constraint_parts:
            part = part.strip()
            if not part:
                continue

            match = self.SIMPLE_CONSTRAINT.match(part)
            if match:
                field = match.group(1)
                operator = match.group(2)
                value = match.group(3).strip()

                if field not in field_constraints:
                    field_constraints[field] = []
                field_constraints[field].append((operator, value))

        # Convert to conditions, detecting ranges
        for field, constraints in field_constraints.items():
            if len(constraints) == 2 and self._is_range(constraints):
                # This is a range condition
                condition = self._create_range_condition(field, constraints)
                if condition:
                    conditions.append(condition)
            else:
                # Simple conditions
                for operator, value in constraints:
                    condition = self._create_simple_condition(field, operator, value)
                    if condition:
                        conditions.append(condition)

        return conditions

    def _split_constraints(self, constraints_str: str) -> list[str]:
        """Split constraints by comma, respecting parentheses and quotes."""
        parts = []
        current = []
        paren_depth = 0
        in_string = False
        string_char = None

        for char in constraints_str:
            if char in ('"', "'") and not in_string:
                in_string = True
                string_char = char
            elif char == string_char and in_string:
                in_string = False
                string_char = None
            elif char == '(' and not in_string:
                paren_depth += 1
            elif char == ')' and not in_string:
                paren_depth -= 1
            elif char == ',' and paren_depth == 0 and not in_string:
                parts.append(''.join(current))
                current = []
                continue

            current.append(char)

        if current:
            parts.append(''.join(current))

        return parts

    def _is_range(self, constraints: list[tuple[str, str]]) -> bool:
        """Check if constraints form a range (min and max bounds)."""
        operators = {c[0] for c in constraints}
        has_lower = bool(operators & {">=", ">"})
        has_upper = bool(operators & {"<=", "<"})
        return has_lower and has_upper

    def _create_range_condition(
        self,
        field: str,
        constraints: list[tuple[str, str]]
    ) -> RangeCondition | None:
        """Create a range condition from min/max constraints."""
        min_value = None
        max_value = None
        min_inclusive = True
        max_inclusive = False

        for operator, value in constraints:
            parsed_value = self._parse_value(value)

            if operator == ">=":
                min_value = parsed_value
                min_inclusive = True
            elif operator == ">":
                min_value = parsed_value
                min_inclusive = False
            elif operator == "<=":
                max_value = parsed_value
                max_inclusive = True
            elif operator == "<":
                max_value = parsed_value
                max_inclusive = False

        return RangeCondition(
            field=field,
            min_value=min_value,
            max_value=max_value,
            min_inclusive=min_inclusive,
            max_inclusive=max_inclusive,
        )

    def _create_simple_condition(
        self,
        field: str,
        operator: str,
        value: str
    ) -> SimpleCondition | None:
        """Create a simple condition."""
        op = self.OPERATOR_MAP.get(operator)
        if op is None:
            return None

        parsed_value = self._parse_value(value)

        return SimpleCondition(
            field=field,
            operator=op,
            value=parsed_value,
        )

    def _parse_value(self, value: str) -> any:
        """Parse a value string into appropriate Python type."""
        value = value.strip()

        # Boolean
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False
        if value.lower() == "null":
            return None

        # String (quoted)
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            return value[1:-1]

        # Numeric
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            pass

        # Return as-is
        return value

    def _parse_then_block(self, then_block: str) -> list[Action]:
        """Parse the then block into actions."""
        actions = []

        # Try SET_FIELD pattern: $binding.setField(value);
        for match in self.SET_FIELD_PATTERN.finditer(then_block):
            binding = match.group(1)
            field = match.group(2).lower()  # setDecision -> decision
            value = self._parse_value(match.group(3))

            actions.append(Action(
                action_type=ActionType.SET_FIELD,
                target=field,
                value=value,
                binding=binding,
            ))

        # Try INSERT pattern: insert(new FactType(value));
        for match in self.INSERT_PATTERN.finditer(then_block):
            fact_type = match.group(1)
            value = self._parse_value(match.group(2))

            actions.append(Action(
                action_type=ActionType.INSERT_FACT,
                target=fact_type,
                value=value,
            ))

        # Try RETRACT pattern: retract($binding);
        for match in self.RETRACT_PATTERN.finditer(then_block):
            binding = match.group(1)

            actions.append(Action(
                action_type=ActionType.RETRACT_FACT,
                target="",
                binding=binding,
            ))

        # Try UPDATE pattern: update($binding);
        for match in self.UPDATE_PATTERN.finditer(then_block):
            binding = match.group(1)

            actions.append(Action(
                action_type=ActionType.UPDATE_FACT,
                target="",
                binding=binding,
            ))

        return actions


def parse_drl(file_path: str | Path) -> RuleSet:
    """Convenience function to parse a DRL file."""
    parser = DRLParser()
    return parser.parse_file(file_path)


def parse_drl_string(content: str, name: str = "ParsedRules") -> RuleSet:
    """Convenience function to parse DRL content string."""
    parser = DRLParser()
    return parser.parse_string(content, name)
