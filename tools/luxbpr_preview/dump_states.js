// Reads {params, per_start, first_index, bars: [[o,h,l,c], ...]} as JSON on stdin and prints, for every bar, the
// committed state of the JavaScript engine as JSON. Used by tests/test_luxbpr_js_parity.py to check the preview
// page's engine against the Python reference.
const LuxBPR = require('./engine.js');

let input = '';
process.stdin.on('data', (d) => { input += d; });
process.stdin.on('end', () => {
  const req = JSON.parse(input);
  const p = req.params || {};
  const e = new LuxBPR.Engine({
    mode: p.mode, presentBars: p.present_bars, length: p.length, percBody: p.perc_body, showFVG: p.show_fvg,
    bpr: p.bpr, fvgMode: p.fvg_mode, visBoxes: p.vis_boxes, bxBack: p.bx_back, ext: p.ext_bars,
  }, req.per_start === null || req.per_start === undefined ? null : req.per_start);
  const ser = (arr) => arr.map((z) => (z.box
    ? [1, z.box.left, z.box.top, z.box.right, z.box.bottom, z.active ? 1 : 0, z.pos, z.box.border, z.box.brokenFill ? 1 : 0]
    : [0, null, null, null, null, z.active ? 1 : 0, z.pos, null, null]));
  const out = [];
  req.bars.forEach((b, i) => {
    e.process(req.first_index + i, b[0], b[1], b[2], b[3]);
    out.push({ fu: ser(e.fu), fd: ser(e.fd), bu: ser(e.bu), bd: ser(e.bd), disp: [e.dispUp ? 1 : 0, e.dispDn ? 1 : 0],
      fib: e.fib() });
  });
  out.push({ events: e.events });
  process.stdout.write(JSON.stringify(out));
});
