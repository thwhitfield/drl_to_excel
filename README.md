# drl_to_excel

Bidirectional converter between Excel decision tables and Drools Rule Language (DRL), with an intermediate representation (IR) for programmatic rule generation.

```
Excel ←→ IR ←→ DRL
          ↑
   Programmatic generation
```

## Installation

```bash
pip install openpyxl
```

## Quick Start

### Excel → DRL

```python
from src.excel_parser import parse_excel
from src.drl_writer import write_drl

# Parse Excel decision table into IR
ruleset = parse_excel("fraud_rules.xlsx")

# Modify rules programmatically
ruleset.rules[0].salience = 100

# Export to DRL
write_drl(ruleset, "fraud_rules.drl")
```

### Programmatic Rule Creation

```python
from src.ir import (
    RuleSet, Rule, FactPattern, Action, ActionType,
    SimpleCondition, RangeCondition, Operator,
    score_threshold, amount_range, decline_action,
)

# Create rules using helper functions
rule = Rule(
    name="HighRiskTransaction",
    fact_patterns=[
        FactPattern(
            fact_type="Transaction",
            binding="tx",
            conditions=[
                score_threshold(">", 0.8),
                amount_range(1000, 10000),
            ]
        )
    ],
    actions=[decline_action()]
)

ruleset = RuleSet(
    name="FraudRules",
    package="com.example.fraud",
    imports=["com.example.model.Transaction"],
    rules=[rule]
)

print(ruleset.to_drl())
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

## Project Structure

```
drl_to_excel/
├── src/
│   ├── ir.py              # Intermediate Representation
│   ├── excel_parser.py    # Excel → IR
│   └── drl_writer.py      # IR → DRL
├── tests/
│   ├── test_ir.py
│   ├── test_excel_parser.py
│   └── fixtures/          # Sample Excel files
└── examples/
    └── excel_to_drl.py    # Example workflow
```

## Running Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

## Roadmap

- [x] **Phase 1**: Core IR + Excel → DRL
- [ ] **Phase 2**: DRL → IR parser
- [ ] **Phase 3**: IR → Excel writer (roundtrip support)
- [ ] **Phase 4**: Programmatic generation API (A/B variants, bucketing helpers)
