"""Build the self-contained BPR live replay page from template.html + engine.js + synth.js.

Usage: python tools/luxbpr_preview/build.py [output.html]
Default output: research/indicators/preview/LuxAlgo_BPR_live_replay.html
"""
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def _block(path: pathlib.Path, begin: str, end: str) -> str:
    text = path.read_text()
    head = text[: text.index(begin)]
    licence = "\n".join(ln for ln in head.splitlines() if ln.startswith("//"))
    return licence + "\n" + text[text.index(begin): text.index(end) + len(end)]


def build(out: pathlib.Path) -> pathlib.Path:
    page = (HERE / "template.html").read_text()
    page = page.replace("/*__ENGINE__*/", _block(HERE / "engine.js", "// ENGINE-BEGIN", "// ENGINE-END"))
    page = page.replace("/*__SYNTH__*/", _block(HERE / "synth.js", "// SYNTH-BEGIN", "// SYNTH-END"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page)
    return out


if __name__ == "__main__":
    target = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "research/indicators/preview/LuxAlgo_BPR_live_replay.html"
    print(build(target))
