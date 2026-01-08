# Drools Decision Table Converter
# Bidirectional conversion between Excel decision tables and DRL

__version__ = "0.1.0"

from drl_to_excel.ir import (
    Operator,
    ActionType,
    Condition,
    SimpleCondition,
    RangeCondition,
    BucketCondition,
    NullCheckCondition,
    FactPattern,
    Action,
    Rule,
    RuleSet,
    score_threshold,
    amount_range,
    category_check,
    decline_action,
    approve_action,
    review_action,
)
from drl_to_excel.excel_parser import ExcelParser, parse_excel
from drl_to_excel.drl_writer import DRLWriter, write_drl

__all__ = [
    # Version
    "__version__",
    # Enums
    "Operator",
    "ActionType",
    # Conditions
    "Condition",
    "SimpleCondition",
    "RangeCondition",
    "BucketCondition",
    "NullCheckCondition",
    # Core IR
    "FactPattern",
    "Action",
    "Rule",
    "RuleSet",
    # Helper factories
    "score_threshold",
    "amount_range",
    "category_check",
    "decline_action",
    "approve_action",
    "review_action",
    # Parsers/Writers
    "ExcelParser",
    "parse_excel",
    "DRLWriter",
    "write_drl",
]
