#!/usr/bin/env python3
"""
Example: Excel → IR → DRL Workflow

This script demonstrates:
1. Loading an Excel decision table
2. Inspecting the IR (Intermediate Representation)
3. Modifying rules programmatically
4. Exporting to DRL format
"""

from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.excel_parser import parse_excel
from src.drl_writer import write_drl, DRLWriter
from src.ir import SimpleCondition, Operator, Action, ActionType


def main():
    # Path to sample Excel file
    excel_path = Path(__file__).parent.parent / "tests" / "fixtures" / "fraud_rules.xlsx"

    print("=" * 60)
    print("Excel → IR → DRL Converter Demo")
    print("=" * 60)

    # Step 1: Parse Excel into IR
    print("\n1. Parsing Excel decision table...")
    ruleset = parse_excel(excel_path)

    print(f"   RuleSet: {ruleset.name}")
    print(f"   Package: {ruleset.package}")
    print(f"   Imports: {len(ruleset.imports)}")
    print(f"   Rules:   {len(ruleset.rules)}")

    # Step 2: Inspect the IR
    print("\n2. Inspecting rules in IR:")
    for rule in ruleset.rules:
        print(f"\n   Rule: {rule.name}")
        for pattern in rule.fact_patterns:
            print(f"      Fact: {pattern.fact_type} (${pattern.binding})")
            for cond in pattern.conditions:
                print(f"         Condition: {cond.to_drl_constraint()}")
        for action in rule.actions:
            print(f"      Action: {action.to_drl()}")

    # Step 3: Modify a rule programmatically
    print("\n3. Modifying rule: Adding higher salience to first rule...")
    ruleset.rules[0].salience = 100
    ruleset.rules[0].description = "High-priority fraud detection rule"

    # Step 4: Add a new condition to an existing rule
    print("   Adding new condition to first rule: check for international transactions...")
    if ruleset.rules[0].fact_patterns:
        ruleset.rules[0].fact_patterns[0].conditions.append(
            SimpleCondition(
                field="isInternational",
                operator=Operator.EQ,
                value=True
            )
        )

    # Step 5: Generate DRL
    print("\n4. Generating DRL output:")
    print("-" * 60)

    drl_content = write_drl(ruleset)
    print(drl_content)

    # Step 6: Save to file
    output_path = Path(__file__).parent / "output" / "fraud_rules.drl"
    output_path.parent.mkdir(exist_ok=True)
    write_drl(ruleset, output_path)
    print("-" * 60)
    print(f"\n5. DRL saved to: {output_path}")

    # Step 7: Demo the advanced writer
    print("\n6. Using advanced DRLWriter with custom formatting...")
    writer = DRLWriter(indent="  ", include_comments=True)
    formatted_drl = writer.write(ruleset)
    print(f"   Generated {len(formatted_drl)} characters of DRL")


if __name__ == "__main__":
    main()
