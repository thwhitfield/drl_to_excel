#!/usr/bin/env python3
"""
Example: A/B Test Variant Generation

This script demonstrates:
1. Creating base fraud detection rules using the fluent RuleBuilder API
2. Generating A/B test variants by sweeping score thresholds
3. Adding bucketing for controlled traffic splitting
4. Exporting variants to both DRL and Excel formats
"""

from pathlib import Path

from drl_to_excel import (
    RuleBuilder,
    RuleSetBuilder,
    generate_threshold_variants,
    generate_bucketed_variants,
    add_bucket_to_rule,
    write_drl,
    write_excel,
)


def main():
    print("=" * 70)
    print("A/B Test Variant Generation Demo")
    print("=" * 70)

    # =========================================================================
    # Example 1: Generate 5 score threshold variants
    # =========================================================================
    print("\n1. Generating score threshold variants...")

    # Create a base rule using the fluent API
    base_rule = (RuleBuilder("HighRiskDecline")
        .with_fact("Transaction", "tx")
        .when_score_above(0.8)
        .when_category("ELECTRONICS")
        .then_decline()
        .with_salience(100)
        .build())

    print(f"   Base rule: {base_rule.name}")
    print(f"   Base threshold: score > 0.8")

    # Generate variants with different thresholds
    thresholds = [0.70, 0.75, 0.80, 0.85, 0.90]
    variants = generate_threshold_variants(
        base_rule,
        field="score",
        thresholds=thresholds,
        variant_group="score_optimization"
    )

    print(f"\n   Generated {len(variants)} variants:")
    for variant in variants:
        cond = variant.fact_patterns[0].conditions[0]
        print(f"      - {variant.name}: score > {cond.value}")

    # =========================================================================
    # Example 2: Create bucketed A/B test (50/50 split)
    # =========================================================================
    print("\n2. Creating bucketed A/B test (50/50 split)...")

    # Control group: current threshold (0.8), bucket 0-4
    control = (RuleBuilder("Control_Threshold_080")
        .with_fact("Transaction", "tx")
        .when_score_above(0.8)
        .when_bucketed("cardLastDigit", [0, 1, 2, 3, 4])
        .then_decline()
        .as_variant("control", "threshold_ab_test")
        .with_description("Control: current 0.8 threshold")
        .build())

    # Treatment group: lower threshold (0.7), bucket 5-9
    treatment = (RuleBuilder("Treatment_Threshold_070")
        .with_fact("Transaction", "tx")
        .when_score_above(0.7)
        .when_bucketed("cardLastDigit", [5, 6, 7, 8, 9])
        .then_decline()
        .as_variant("treatment", "threshold_ab_test")
        .with_description("Treatment: experimental 0.7 threshold")
        .build())

    print(f"   Control: score > 0.8, buckets [0-4] (50% traffic)")
    print(f"   Treatment: score > 0.7, buckets [5-9] (50% traffic)")

    # =========================================================================
    # Example 3: Multi-arm bandit style (5 equal buckets)
    # =========================================================================
    print("\n3. Generating multi-arm test (5 variants, 20% each)...")

    base_for_buckets = (RuleBuilder("MultiArmTest")
        .with_fact("Transaction", "tx")
        .when_score_above(0.8)
        .then_decline()
        .build())

    # Generate 5 bucketed variants
    multi_arm_variants = generate_bucketed_variants(
        base_for_buckets,
        field="cardLastDigit",
        num_buckets=5,
        variant_group="multi_arm_test"
    )

    # Modify each variant to have a different threshold
    for i, (variant, threshold) in enumerate(zip(multi_arm_variants, thresholds)):
        # Update the score condition
        variant.fact_patterns[0].conditions = [
            cond for cond in variant.fact_patterns[0].conditions
            if not (hasattr(cond, 'field') and cond.field == 'score')
        ]
        from drl_to_excel import score_threshold
        variant.fact_patterns[0].conditions.insert(0, score_threshold(">", threshold))
        variant.description = f"Arm {i}: threshold={threshold}, buckets={i*2}-{i*2+1}"

    print("   Generated variants:")
    for v in multi_arm_variants:
        print(f"      - {v.name}: {v.description}")

    # =========================================================================
    # Build and export RuleSet
    # =========================================================================
    print("\n4. Building and exporting rulesets...")

    # Combine all variants into a ruleset
    all_rules = variants + [control, treatment] + multi_arm_variants

    ruleset = (RuleSetBuilder("FraudABTests")
        .package("com.example.fraud.abtest")
        .imports([
            "com.example.model.Transaction",
            "com.example.model.Result"
        ])
        .add_rules(all_rules)
        .build())

    # Create output directory
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)

    # Export to DRL
    drl_path = output_dir / "ab_test_rules.drl"
    drl_content = write_drl(ruleset, drl_path)
    print(f"   DRL exported to: {drl_path}")

    # Export to Excel
    excel_path = output_dir / "ab_test_rules.xlsx"
    write_excel(ruleset, excel_path)
    print(f"   Excel exported to: {excel_path}")

    # =========================================================================
    # Show sample DRL output
    # =========================================================================
    print("\n5. Sample DRL output (first 2 rules):")
    print("-" * 70)

    # Parse and show first 2 rules
    lines = drl_content.split("\n")
    rule_count = 0
    for line in lines:
        print(line)
        if line.strip() == "end":
            rule_count += 1
            if rule_count >= 2:
                print("...")
                break

    print("-" * 70)

    # =========================================================================
    # Summary
    # =========================================================================
    print("\nSummary:")
    print(f"   Total rules generated: {len(all_rules)}")
    print(f"   - Threshold sweep variants: {len(variants)}")
    print(f"   - A/B test (control + treatment): 2")
    print(f"   - Multi-arm variants: {len(multi_arm_variants)}")
    print("\nFiles created:")
    print(f"   - {drl_path}")
    print(f"   - {excel_path}")


if __name__ == "__main__":
    main()
