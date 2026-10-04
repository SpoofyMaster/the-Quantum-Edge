# Compilation report — `mql5/VideoStrategyEA`

**Result: NOT COMPILED.** The build sandbox has no MetaEditor/MetaTrader 5 and cannot install one (download hosts for
MetaQuotes and Wine are blocked by the network policy). Nothing in this project claims that the EA compiles until you
compile it and report back.

## What was checked instead (executed in this repository)
| Check | How | Result |
|---|---|---|
| Bracket/brace/parenthesis balance outside strings and comments, all 9 files | `python tools/mql5_static_check.py mql5/VideoStrategyEA` | balanced |
| Every `#include "..."` resolves | same checker | all resolve |
| Every called function / method name is defined in the sources, is an MQL5 built-in, or is a `CTrade` method | same checker (name-level, not type-level) | no undefined names |
| Each algorithm (pivots, extension tracker, zig-zag, MTF context, location, type-3 shift, DXY gate, sizing rule) mirrors a Python function that is unit-tested | `tests/test_video_*.py` in CI (`tests` workflow) | Python side: passing in CI |
| Manual review for known MQL5 pitfalls | by hand | fixed: explicit `(ulong)` casts for `CTrade` deviation/magic, `(long)` for `HistorySelectByPosition`, `MathMax(0.0, …)` overload, unused variable, breaker reset per FX day, missed-close re-sync |

The checker is not a compiler: it cannot find type errors, wrong overloads, const-correctness errors or
missing semicolons inside expressions. Expect a short list of compiler messages on the first build.

## What to do (U-5 in docs/BACKLOG.md)
1. Copy `mql5/VideoStrategyEA/` (the `.mq5` and `include/`) to `MQL5/Experts/`.
2. Open `VideoStrategyEA.mq5` in MetaEditor and press F7.
3. Paste the complete "Errors" tab (errors **and** warnings, with line numbers) into the conversation.
Target: 0 errors, 0 warnings. Each fix will be mirrored in the Python reference if it touches logic.

## Expected warnings that are acceptable
None are expected. If MetaEditor reports "possible loss of data due to type conversion", it should be fixed with an
explicit cast, not ignored.
