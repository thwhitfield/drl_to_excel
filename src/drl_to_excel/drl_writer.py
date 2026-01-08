"""
DRL Writer.

Serializes IR (RuleSet) to Drools Rule Language (DRL) files.
"""

from pathlib import Path
from drl_to_excel.ir import RuleSet


def write_drl(ruleset: RuleSet, file_path: str | Path | None = None) -> str:
    """
    Write a RuleSet to DRL format.

    Args:
        ruleset: The RuleSet to serialize
        file_path: Optional path to write the DRL file

    Returns:
        The DRL content as a string
    """
    drl_content = ruleset.to_drl()

    if file_path:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(drl_content)

    return drl_content


class DRLWriter:
    """
    Advanced DRL writer with formatting options.

    For most use cases, the simple write_drl() function is sufficient.
    This class provides additional control over formatting.
    """

    def __init__(
        self,
        indent: str = "    ",
        include_disabled: bool = False,
        include_comments: bool = True,
    ):
        self.indent = indent
        self.include_disabled = include_disabled
        self.include_comments = include_comments

    def write(self, ruleset: RuleSet, file_path: str | Path | None = None) -> str:
        """Write RuleSet to DRL with custom formatting."""
        lines = []

        # Header comment
        if self.include_comments:
            lines.append(f"// Generated from RuleSet: {ruleset.name}")
            if ruleset.rule_table_name:
                lines.append(f"// Decision Table: {ruleset.rule_table_name}")
            lines.append("")

        # Package
        lines.append(f"package {ruleset.package};")
        lines.append("")

        # Imports
        for imp in ruleset.imports:
            lines.append(f"import {imp};")
        if ruleset.imports:
            lines.append("")

        # Globals
        for name, type_name in ruleset.globals.items():
            lines.append(f"global {type_name} {name};")
        if ruleset.globals:
            lines.append("")

        # Rules
        for rule in ruleset.rules:
            if not rule.enabled and not self.include_disabled:
                continue

            # Rule comment with description
            if self.include_comments and rule.description:
                lines.append(f"// {rule.description}")

            # Rule definition
            lines.append(self._format_rule(rule))
            lines.append("")

        content = "\n".join(lines)

        if file_path:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)

        return content

    def _format_rule(self, rule) -> str:
        """Format a single rule with custom indentation."""
        lines = []

        # Rule declaration
        lines.append(f'rule "{rule.name}"')

        # Attributes
        if rule.salience is not None:
            lines.append(f"{self.indent}salience {rule.salience}")
        if not rule.enabled:
            lines.append(f"{self.indent}enabled false")

        # Variant metadata as rule attribute (if present)
        if rule.variant_id:
            lines.append(f'{self.indent}// variant-id: {rule.variant_id}')
        if rule.variant_group:
            lines.append(f'{self.indent}// variant-group: {rule.variant_group}')

        # When clause
        lines.append(f"{self.indent}when")
        for pattern in rule.fact_patterns:
            lines.append(f"{self.indent}{self.indent}{pattern.to_drl()}")

        # Then clause
        lines.append(f"{self.indent}then")
        for action in rule.actions:
            lines.append(f"{self.indent}{self.indent}{action.to_drl()}")

        lines.append("end")

        return "\n".join(lines)
