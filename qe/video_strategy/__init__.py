"""Reference implementation of the tomtrades "gold reversal + DXY entry-model inversion" strategy.

Executable specification for research/ALGORITHM_SPECIFICATION.md. The MQL5 EA in mql5/VideoStrategyEA mirrors these
functions one-to-one. Rule IDs (EXT-2, SHF-3, COR-1, ...) refer to research/STRATEGY_RULEBOOK.md.
"""
from .params import Params, m15_preset  # noqa: F401
