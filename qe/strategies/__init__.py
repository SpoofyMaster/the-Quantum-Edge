"""Trading-strategy references built on the indicator ports.

``bpr_fvg``: the pure-Python reference of the BPR + FVG Expert Advisor's trading logic
(research/indicators/BPR_FVG_EA_SPEC.md), plus a bar-based execution simulator. Its zones come from the port of
the FVG / Balance Price Range logic of "ICT Concepts [LuxAlgo]".
(c) LuxAlgo (original Pine v5 logic of 'ICT Concepts [LuxAlgo]'), licensed CC BY-NC-SA 4.0
(https://creativecommons.org/licenses/by-nc-sa/4.0/). The port is a derivative work for non-commercial use;
its changes are listed in research/indicators/LUXALGO_BPR_SPEC.md section 10.
"""
from qe.strategies.bpr_fvg import (
    Env,
    Intent,
    Setup,
    SetupDetector,
    SimResult,
    StrategyParams,
    harness_run,
    simulate,
)

__all__ = [
    "Env",
    "Intent",
    "Setup",
    "SetupDetector",
    "SimResult",
    "StrategyParams",
    "harness_run",
    "simulate",
]
