#!/usr/bin/env python3
"""MT5 -> Python parity check for the LuxAlgo FVG / BPR port.

Licence and attribution
-----------------------
(c) LuxAlgo (original Pine v5 logic of 'ICT Concepts [LuxAlgo]').
Licensed under CC BY-NC-SA 4.0: https://creativecommons.org/licenses/by-nc-sa/4.0/
This tool is part of a port (a derivative work) of the FVG / BPR logic of that Pine v5 script, for
non-commercial research use only, shared under the same licence. The changes made by the ports are listed in
research/indicators/LUXALGO_BPR_SPEC.md section 10.

Usage
-----
    python tools/luxbpr_parity.py <export.csv>

Reads the text export written by the MT5 indicator, replays its BAR rows through the Python reference
``qe.indicators.luxalgo_bpr.LuxBprEngine`` with the exported parameters, and compares every ZONE row field by
field with the committed Python state after the last exported bar.

Exit codes: 0 = identical, 1 = at least one mismatch, 2 = the file could not be read or is malformed.

Export format (one record per line, comma separated, '.' decimal point, prices with 17 significant digits)::

    # LuxAlgo_BPR export v1
    PARAMS,<Present|Historical>,<present_bars>,<length>,<show_fvg 0|1>,<bpr 0|1>,<FVG|IFVG>,<vis_boxes>,
           <per_start|NA>,<first_index>,<last_committed_index>                       (one line)
    BAR,<index>,<time_unix>,<open>,<high>,<low>,<close>
    ZONE,<FVG_UP|FVG_DN|BPR_UP|BPR_DN>,<slot>,<exists 0|1>,<left>,<top>,<right>,<bottom>,<active 0|1>,
         <pos -1|1|NA>,<solid|dashed|dotted>,<broken_fill 0|1>                       (one line)

Prices are compared with an absolute tolerance of ``1e-9 * price_scale`` where ``price_scale`` is
``max(1, max |price| over the BAR rows)``; integers, flags and styles must match exactly. For a slot that has
no box on both sides (``exists = 0``) only ``active`` and ``pos`` are compared.

Standard library only.
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

try:  # normal import when the repository root is on sys.path
    from qe.indicators.luxalgo_bpr import BprParams, LuxBprEngine, Zone
except ImportError:  # executed as `python tools/luxbpr_parity.py` from anywhere
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from qe.indicators.luxalgo_bpr import BprParams, LuxBprEngine, Zone

HEADER = "# LuxAlgo_BPR export v1"
KINDS = ("FVG_UP", "FVG_DN", "BPR_UP", "BPR_DN")
PRICE_RTOL = 1e-9
MAX_REPORTED = 200


class ExportFormatError(ValueError):
    """The export file is malformed."""


@dataclass
class ZoneRow:
    kind: str
    slot: int
    exists: int
    left: int | None
    top: float | None
    right: int | None
    bottom: float | None
    active: int
    pos: int | None
    border: str | None
    broken_fill: int | None
    line_no: int = 0


@dataclass
class Export:
    params: BprParams
    per_start: int | None
    first_index: int
    last_index: int
    bars: list[tuple[int, int, float, float, float, float]] = field(default_factory=list)
    zones: list[ZoneRow] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------------------------- formatting
def _fmt_price(x: float) -> str:
    return format(float(x), ".17g")


def _fmt_opt_int(x: int | None) -> str:
    return "NA" if x is None else str(int(x))


def _zone_fields(z: Zone) -> list[str]:
    """exists, left, top, right, bottom, active, pos, border, broken_fill of one slot."""
    if z.box is None:
        return ["0", "NA", "NA", "NA", "NA", "1" if z.active else "0", _fmt_opt_int(z.pos), "solid", "0"]
    b = z.box
    return [
        "1",
        str(int(b.left)),
        _fmt_price(b.top),
        str(int(b.right)),
        _fmt_price(b.bottom),
        "1" if z.active else "0",
        _fmt_opt_int(z.pos),
        b.border,
        "1" if b.broken_fill else "0",
    ]


def write_export(
    engine: LuxBprEngine,
    bars: Sequence[Sequence[float]],
    first_index: int,
    params: BprParams,
    per_start: int | None,
    path: str | Path,
) -> None:
    """Write ``engine``'s committed state in the MT5 export format (used for round-trip tests).

    ``bars`` are the bars the engine processed, in order, each ``(open, high, low, close)`` or
    ``(time_unix, open, high, low, close)``; with 4-tuples ``time_unix`` is written as 0.
    """
    if engine.last_index is None:
        raise ValueError("engine has not processed any bar")
    if params != engine.params:
        raise ValueError("params differ from engine.params")
    if per_start != engine.per_start:
        raise ValueError("per_start differs from engine.per_start")
    default = BprParams()
    for name in ("perc_body", "bx_back", "ext_bars"):
        if getattr(params, name) != getattr(default, name):
            raise ValueError(f"{name} is not part of the export format and must keep its default")
    if first_index + len(bars) - 1 != engine.last_index:
        raise ValueError(
            f"bars cover {first_index}..{first_index + len(bars) - 1} but the engine's last bar is {engine.last_index}"
        )
    lines = [HEADER]
    lines.append(
        ",".join(
            [
                "PARAMS",
                params.mode,
                str(params.present_bars),
                str(params.length),
                "1" if params.show_fvg else "0",
                "1" if params.bpr else "0",
                params.fvg_mode,
                str(params.vis_boxes),
                _fmt_opt_int(per_start),
                str(first_index),
                str(engine.last_index),
            ]
        )
    )
    for i, bar in enumerate(bars):
        if len(bar) == 5:
            t, o, h, l, c = bar  # noqa: E741
        elif len(bar) == 4:
            t = 0
            o, h, l, c = bar  # noqa: E741
        else:
            raise ValueError(f"bar {i} must have 4 or 5 values")
        lines.append(",".join(["BAR", str(first_index + i), str(int(t))] + [_fmt_price(v) for v in (o, h, l, c)]))
    for kind, arr in zip(KINDS, (engine.fvg_up, engine.fvg_dn, engine.bpr_up, engine.bpr_dn)):
        for slot, z in enumerate(arr):
            lines.append(",".join(["ZONE", kind, str(slot)] + _zone_fields(z)))
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------------------------- parsing
def _read_text(path: str | Path) -> str:
    raw = Path(path).read_bytes()
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):  # MT5 FILE_UNICODE writes UTF-16 with BOM
        return raw.decode("utf-16")
    return raw.decode("utf-8-sig")


def _int(tok: str, what: str, line_no: int) -> int:
    try:
        v = float(tok)
    except ValueError:
        raise ExportFormatError(f"line {line_no}: {what} is not a number: {tok!r}") from None
    if not math.isfinite(v) or v != int(v):
        raise ExportFormatError(f"line {line_no}: {what} is not an integer: {tok!r}")
    return int(v)


def _opt_int(tok: str, what: str, line_no: int) -> int | None:
    return None if tok.upper() == "NA" else _int(tok, what, line_no)


def _float(tok: str, what: str, line_no: int) -> float:
    try:
        return float(tok)
    except ValueError:
        raise ExportFormatError(f"line {line_no}: {what} is not a number: {tok!r}") from None


def _opt_float(tok: str, what: str, line_no: int) -> float | None:
    return None if tok.upper() == "NA" else _float(tok, what, line_no)


def _flag(tok: str, what: str, line_no: int) -> int:
    v = _int(tok, what, line_no)
    if v not in (0, 1):
        raise ExportFormatError(f"line {line_no}: {what} must be 0 or 1, got {tok!r}")
    return v


def parse_export(path: str | Path) -> Export:
    """Parse an export file. Raises ``ExportFormatError`` on malformed content."""
    text = _read_text(path)
    lines = [ln.strip() for ln in text.splitlines()]
    numbered = [(i + 1, ln) for i, ln in enumerate(lines) if ln]
    if not numbered or numbered[0][1] != HEADER:
        raise ExportFormatError(f"first line must be {HEADER!r}")
    params_row: tuple[int, list[str]] | None = None
    bars: list[tuple[int, int, float, float, float, float]] = []
    zones: list[ZoneRow] = []
    for line_no, ln in numbered[1:]:
        if ln.startswith("#"):
            continue
        tok = [t.strip() for t in ln.split(",")]
        rec = tok[0]
        if rec == "PARAMS":
            if params_row is not None:
                raise ExportFormatError(f"line {line_no}: second PARAMS row")
            if len(tok) != 11:
                raise ExportFormatError(f"line {line_no}: PARAMS needs 11 fields, got {len(tok)}")
            params_row = (line_no, tok)
        elif rec == "BAR":
            if len(tok) != 7:
                raise ExportFormatError(f"line {line_no}: BAR needs 7 fields, got {len(tok)}")
            bars.append(
                (
                    _int(tok[1], "BAR index", line_no),
                    _int(tok[2], "BAR time", line_no),
                    _float(tok[3], "open", line_no),
                    _float(tok[4], "high", line_no),
                    _float(tok[5], "low", line_no),
                    _float(tok[6], "close", line_no),
                )
            )
        elif rec == "ZONE":
            if len(tok) != 12:
                raise ExportFormatError(f"line {line_no}: ZONE needs 12 fields, got {len(tok)}")
            kind = tok[1]
            if kind not in KINDS:
                raise ExportFormatError(f"line {line_no}: unknown ZONE kind {kind!r}")
            border = None if tok[10].upper() == "NA" else tok[10]
            if border is not None and border not in ("solid", "dashed", "dotted"):
                raise ExportFormatError(f"line {line_no}: unknown border style {tok[10]!r}")
            zones.append(
                ZoneRow(
                    kind=kind,
                    slot=_int(tok[2], "slot", line_no),
                    exists=_flag(tok[3], "exists", line_no),
                    left=_opt_int(tok[4], "left", line_no),
                    top=_opt_float(tok[5], "top", line_no),
                    right=_opt_int(tok[6], "right", line_no),
                    bottom=_opt_float(tok[7], "bottom", line_no),
                    active=_flag(tok[8], "active", line_no),
                    pos=_opt_int(tok[9], "pos", line_no),
                    border=border,
                    broken_fill=None if tok[11].upper() == "NA" else _flag(tok[11], "broken_fill", line_no),
                    line_no=line_no,
                )
            )
        else:
            raise ExportFormatError(f"line {line_no}: unknown record type {rec!r}")
    if params_row is None:
        raise ExportFormatError("no PARAMS row")
    line_no, tok = params_row
    warnings: list[str] = []
    mode = tok[1]
    fvg_mode = tok[6]
    try:
        params = BprParams(
            mode=mode,
            present_bars=_int(tok[2], "present_bars", line_no),
            length=_int(tok[3], "length", line_no),
            show_fvg=bool(_flag(tok[4], "show_fvg", line_no)),
            bpr=bool(_flag(tok[5], "bpr", line_no)),
            fvg_mode=fvg_mode,
            vis_boxes=_int(tok[7], "vis_boxes", line_no),
        )
    except ValueError as exc:
        if isinstance(exc, ExportFormatError):
            raise
        raise ExportFormatError(f"line {line_no}: invalid PARAMS: {exc}") from None
    per_start = _opt_int(tok[8], "per_start", line_no)
    first_index = _int(tok[9], "first_index", line_no)
    last_index = _int(tok[10], "last_committed_index", line_no)
    if params.mode == "Present" and per_start is None:
        raise ExportFormatError(f"line {line_no}: Present mode needs a numeric per_start")
    if params.mode == "Historical" and per_start is not None:
        warnings.append(f"Historical mode with per_start={per_start}: per_start ignored (always in window)")
        per_start = None
    # bars must be consecutive first_index..last_index
    if not bars:
        raise ExportFormatError("no BAR rows")
    for k, b in enumerate(bars):
        if b[0] != first_index + k:
            raise ExportFormatError(f"BAR rows not consecutive: row {k} has index {b[0]}, expected {first_index + k}")
    if bars[-1][0] != last_index:
        raise ExportFormatError(f"last BAR index {bars[-1][0]} != last_committed_index {last_index}")
    expected_first = 0 if per_start is None else max(0, per_start - params.length - 3)
    if first_index > expected_first:
        warnings.append(
            f"first_index={first_index} > {expected_first}: the replay may lack warm-up bars, so a mismatch can be "
            "caused by the export window rather than by the port"
        )
    return Export(params, per_start, first_index, last_index, bars, zones, warnings)


# ---------------------------------------------------------------------------------------------- comparison
def replay(export: Export) -> LuxBprEngine:
    """Run the Python reference over the exported bars with the exported parameters."""
    eng = LuxBprEngine(export.params, export.per_start)
    for idx, _t, o, h, l, c in export.bars:  # noqa: E741
        eng.process_bar(idx, o, h, l, c)
    return eng


def _price_scale(export: Export) -> float:
    scale = 1.0
    for _i, _t, o, h, l, c in export.bars:  # noqa: E741
        scale = max(scale, abs(o), abs(h), abs(l), abs(c))
    return scale


def compare(export: Export, engine: LuxBprEngine | None = None) -> list[str]:
    """Return a list of human-readable mismatches (empty list = identical)."""
    eng = replay(export) if engine is None else engine
    tol = PRICE_RTOL * _price_scale(export)
    arrays = {"FVG_UP": eng.fvg_up, "FVG_DN": eng.fvg_dn, "BPR_UP": eng.bpr_up, "BPR_DN": eng.bpr_dn}
    mismatches: list[str] = []
    seen: dict[tuple[str, int], ZoneRow] = {}
    for row in export.zones:
        key = (row.kind, row.slot)
        if key in seen:
            mismatches.append(f"line {row.line_no}: duplicate ZONE {row.kind}[{row.slot}]")
            continue
        seen[key] = row
    for kind, arr in arrays.items():
        for slot, z in enumerate(arr):
            row = seen.get((kind, slot))
            tag = f"{kind}[{slot}]"
            if row is None:
                mismatches.append(f"{tag}: missing in export (python has {'a box' if z.box else 'no box'})")
                continue
            py_exists = 0 if z.box is None else 1
            if row.exists != py_exists:
                mismatches.append(f"{tag} exists: mt5={row.exists} py={py_exists} (line {row.line_no})")
                continue
            checks: list[tuple[str, object, object, bool]] = []
            if z.box is not None:
                b = z.box
                checks += [
                    ("left", row.left, b.left, False),
                    ("top", row.top, b.top, True),
                    ("right", row.right, b.right, False),
                    ("bottom", row.bottom, b.bottom, True),
                ]
            checks += [("active", row.active, 1 if z.active else 0, False), ("pos", row.pos, z.pos, False)]
            if z.box is not None:
                checks += [
                    ("border", row.border, z.box.border, False),
                    ("broken_fill", row.broken_fill, 1 if z.box.broken_fill else 0, False),
                ]
            for name, mt5_v, py_v, is_price in checks:
                if is_price:
                    ok = mt5_v is not None and py_v is not None and abs(float(mt5_v) - float(py_v)) <= tol
                else:
                    ok = mt5_v == py_v
                if not ok:
                    mismatches.append(f"{tag} {name}: mt5={_show(mt5_v)} py={_show(py_v)} (line {row.line_no})")
    for (kind, slot), row in seen.items():
        if slot < 0 or slot >= len(arrays[kind]):
            mismatches.append(
                f"line {row.line_no}: unexpected ZONE {kind}[{slot}] (python array has {len(arrays[kind])} slots)"
            )
    return mismatches


def _show(v: object) -> str:
    if v is None:
        return "NA"
    if isinstance(v, float):
        return _fmt_price(v)
    return str(v)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1 or args[0] in ("-h", "--help"):
        print("usage: python tools/luxbpr_parity.py <export.csv>   (exit 0 identical, 1 mismatch, 2 bad input)")
        return 2
    path = args[0]
    try:
        export = parse_export(path)
    except (OSError, UnicodeDecodeError, ExportFormatError) as exc:
        print(f"ERROR: cannot use {path}: {exc}")
        return 2
    p = export.params
    print(f"file: {path}")
    print(
        f"params: mode={p.mode} present_bars={p.present_bars} length={p.length} show_fvg={int(p.show_fvg)} "
        f"bpr={int(p.bpr)} fvg_mode={p.fvg_mode} vis_boxes={p.vis_boxes} per_start="
        f"{'NA' if export.per_start is None else export.per_start}"
    )
    print(f"bars: {len(export.bars)} ({export.first_index}..{export.last_index})")
    for w in export.warnings:
        print(f"WARNING: {w}")
    try:
        mismatches = compare(export)
    except ValueError as exc:
        print(f"ERROR: replay failed: {exc}")
        return 2
    print(f"zone rows: {len(export.zones)}; mismatches: {len(mismatches)}")
    for m in mismatches[:MAX_REPORTED]:
        print(f"MISMATCH {m}")
    if len(mismatches) > MAX_REPORTED:
        print(f"... {len(mismatches) - MAX_REPORTED} more mismatches not shown")
    print("RESULT: IDENTICAL" if not mismatches else "RESULT: MISMATCH")
    return 0 if not mismatches else 1


if __name__ == "__main__":
    sys.exit(main())
