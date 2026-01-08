# drl_to_excel

Bidirectional converter between Excel decision tables and Drools Rule Language (DRL), with an intermediate representation (IR) for programmatic rule generation.

```
Excel ←→ IR ←→ DRL
          ↑
   Programmatic generation
```

## Installation

```bash
# From source (development)
pip install -e ".[dev]"

# Or with conda
cd setup
conda env create -f environment.yml
conda activate drl_to_excel
```

## Quick Start

### Excel → DRL

```python
from drl_to_excel import parse_excel, write_drl

# Parse Excel decision table into IR
ruleset = parse_excel("fraud_rules.xlsx")

# Modify rules programmatically
ruleset.rules[0].salience = 100

# Export to DRL
write_drl(ruleset, "fraud_rules.drl")
```

### DRL → Excel (Roundtrip)

```python
from drl_to_excel import parse_drl, write_excel

# Parse DRL file into IR
ruleset = parse_drl("fraud_rules.drl")

# Export back to Excel
write_excel(ruleset, "fraud_rules.xlsx")
```

### Fluent Rule Builder API

```python
from drl_to_excel import RuleBuilder, RuleSetBuilder, write_drl

# Create rules using the fluent API
rule = (RuleBuilder("HighRiskTransaction")
    .with_fact("Transaction", "tx")
    .when_score_above(0.8)
    .when_amount_between(1000, 10000)
    .when_category("ELECTRONICS")
    .then_decline()
    .with_salience(100)
    .build())

ruleset = (RuleSetBuilder("FraudRules")
    .package("com.example.fraud")
    .imports(["com.example.model.Transaction"])
    .add_rule(rule)
    .build())

print(ruleset.to_drl())
```

### A/B Test Variant Generation

```python
from drl_to_excel import (
    RuleBuilder, generate_threshold_variants, write_drl
)

# Create base rule
base_rule = (RuleBuilder("HighScoreDecline")
    .with_fact("Transaction", "tx")
    .when_score_above(0.8)
    .then_decline()
    .build())

# Generate 5 variants with different thresholds
variants = generate_threshold_variants(
    base_rule,
    field="score",
    thresholds=[0.7, 0.75, 0.8, 0.85, 0.9],
    variant_group="score_ab_test"
)
```

### Bucketed A/B Testing

```python
from drl_to_excel import RuleBuilder

# Control group: 50% of traffic (card digits 0-4)
control = (RuleBuilder("Control")
    .with_fact("Transaction", "tx")
    .when_score_above(0.8)
    .when_bucketed("cardLastDigit", [0, 1, 2, 3, 4])
    .then_decline()
    .as_variant("control", "threshold_test")
    .build())

# Treatment group: 50% of traffic (card digits 5-9)
treatment = (RuleBuilder("Treatment")
    .with_fact("Transaction", "tx")
    .when_score_above(0.7)
    .when_bucketed("cardLastDigit", [5, 6, 7, 8, 9])
    .then_decline()
    .as_variant("treatment", "threshold_test")
    .build())
```

## Excel Format

The parser expects standard Drools decision table format:

| Row | Content |
|-----|---------|
| 1 | `RuleSet` \| package \| `Import` \| class1, class2... |
| 2 | `RuleTable TableName` |
| 3 | `CONDITION` \| `CONDITION` \| ... \| `ACTION` |
| 4 | `$tx : Transaction` \| `$tx : Transaction` \| ... \| `$result : Result` |
| 5 | `score > $1` \| `amount >= $1, amount < $2` \| ... \| `decision = "$1"` |
| 6 | Score Threshold \| Amount Range \| ... \| Decision |
| 7+ | Data rows |

## IR Components

| Class | Purpose |
|-------|---------|
| `SimpleCondition` | Field comparisons (`score > 0.8`, `category == "X"`) |
| `RangeCondition` | Numeric ranges (`100 <= amount < 500`) |
| `BucketCondition` | A/B test bucketing (`card_digit % 10 in [0,1,2]`) |
| `FactPattern` | Drools fact with binding + conditions |
| `Action` | SET_FIELD, INSERT, RETRACT, UPDATE, LOG |
| `Rule` | Single rule with patterns, actions, salience |
| `RuleSet` | Top-level container with package, imports, rules |

## Generation API

| Function | Purpose |
|----------|---------|
| `generate_threshold_variants()` | Sweep a parameter across multiple values |
| `generate_bucketed_variants()` | Create N equal traffic buckets |
| `add_bucket_to_rule()` | Add bucketing condition to existing rule |
| `RuleBuilder` | Fluent API for building rules |
| `RuleSetBuilder` | Fluent API for building rule sets |

## Project Structure

```
drl_to_excel/
├── src/
│   └── drl_to_excel/
│       ├── __init__.py       # Package exports
│       ├── ir.py             # Intermediate Representation
│       ├── excel_parser.py   # Excel → IR
│       ├── excel_writer.py   # IR → Excel
│       ├── drl_parser.py     # DRL → IR
│       ├── drl_writer.py     # IR → DRL
│       └── generators.py     # A/B variant generation
├── tests/
│   ├── test_ir.py
│   ├── test_excel_parser.py
│   ├── test_excel_writer.py
│   ├── test_drl_parser.py
│   ├── test_generators.py
│   └── fixtures/             # Sample Excel files
├── examples/
│   ├── excel_to_drl.py       # Basic workflow
│   └── ab_variants.py        # A/B test generation
├── setup/
│   └── environment.yml       # Conda environment
└── pyproject.toml            # Package configuration
```

## Running Tests

```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
```

## Roadmap

- [x] **Phase 1**: Core IR + Excel → DRL
- [x] **Phase 2**: DRL → IR parser
- [x] **Phase 3**: IR → Excel writer (roundtrip support)
- [x] **Phase 4**: Programmatic generation API (A/B variants, bucketing helpers)
