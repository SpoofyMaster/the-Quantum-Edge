"""Transliterate mql5/Indicators/LuxAlgo_BPR/LuxAlgo_BPR.mq5 into C++ so that its logic can be compiled with g++ and
compared bar by bar with the Python reference (tests/test_luxbpr_mql5_harness.py).

This checks the indicator's LOGIC only. It does not prove that MetaEditor compiles the file: g++ accepts constructs
that MQL5 rejects and the MT5 API is replaced by stubs (shim.h).

Usage: python tools/mql5_cpp_harness/mq5_to_cpp.py <in.mq5> <out.cpp>
"""
import re
import sys


def transform(src: str) -> str:
    out = []
    for line in src.split("\n"):
        if line.startswith("#property") or line.startswith("input group"):
            continue
        if line.startswith("input "):
            line = line[len("input "):]
        out.append(line)
    s = "\n".join(out)
    s = re.sub(r"C'(\d+),(\d+),(\d+)'", r"RGBC(\1,\2,\3)", s)
    # MQL5 array parameters 'const double &x[]' -> C++ pointers
    s = re.sub(r"(const\s+)?(\w+)\s*&\s*(\w+)\[\]", lambda m: (m.group(1) or "") + m.group(2) + " *" + m.group(3), s)
    s, k1 = re.subn(r'#define\s+LXB_PREFIX\s+"LXBPR_"', '#define LXB_PREFIX std::string("LXBPR_")', s)
    s, k2 = re.subn(r"double\s+g_bufUp\[\];", "double g_bufUp[MAXBARS];", s)
    s, k3 = re.subn(r"double\s+g_bufDn\[\];", "double g_bufDn[MAXBARS];", s)
    # any other dynamic array declaration (e.g. a local 'datetime t[];') becomes a fixed-size array
    s = re.sub(r"^(\s*)(double|datetime|int|long)\s+(\w+)\[\];", r"\1static \2 \3[MAXBARS];", s, flags=re.M)
    if (k1, k2, k3) != (1, 1, 1):
        raise SystemExit(f"mq5_to_cpp: expected declarations not found ({k1},{k2},{k3}); update the transform")
    return '#include "shim.h"\n' + s


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as f:
        text = f.read()
    with open(sys.argv[2], "w", encoding="utf-8") as f:
        f.write(transform(text))
