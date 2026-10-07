# MQL5 → C++ logic harness

`tests/test_luxbpr_mql5_harness.py` uses these files to check the MT5 indicator
`mql5/Indicators/LuxAlgo_BPR/LuxAlgo_BPR.mq5` against the Python reference `qe/indicators/luxalgo_bpr.py`.

## How it works

1. `mq5_to_cpp.py` transliterates the `.mq5` into C++:
   - drops `#property` and `input group` lines;
   - turns `C'r,g,b'` colour literals into numbers;
   - turns array parameters into pointers.
2. `shim.h` replaces the MT5 API (objects, buffers, files, alerts) with stubs.
3. `luxbpr_main.cpp` drives `OnInit`/`OnCalculate` as MT5 would:
   - one full calculation at load;
   - then every new bar, each delivered in several ticks;
   - optionally a full reload (`prev_calculated = 0`).

   It prints the committed state and the forming-bar state after every bar.

## What it proves and what it does not

| | |
|---|---|
| **Proves** | The indicator's BPR/FVG logic, its committed-vs-forming-bar split, the Present window, the displacement buffers, the alert count and the parity export all match the Python reference bar for bar. |
| **Does not prove** | That MetaEditor compiles the file (g++ accepts things MQL5 rejects), or how MT5 draws the objects. Compile it in MetaEditor and send the messages. |

Requires `g++` (C++17). The test is skipped when `g++` is missing.
