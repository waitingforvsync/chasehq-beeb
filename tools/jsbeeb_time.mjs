// Time a loop in headless jsbeeb with the real IRQ: the cycles between successive arrivals at a label.
//
//   node tools/jsbeeb_time.mjs [--label game.loop] [--loops 50] [--png build/shot.png] [--model B-DFS1.2]
//                              [--disc build/chasehq.ssd] [--symbols build/chasehq.json]
//
// Prints the median, min and max cycles a loop, and in frames (39,936 cycles); with --png, a screenshot of
// the display after the last loop.

import { writeFileSync } from "node:fs";
import { bootDisc, runTo, symbols } from "./jsbeeb.mjs";

const args = Object.fromEntries(process.argv.slice(2).reduce((a, x, i, all) =>
    x.startsWith("--") ? [...a, [x.slice(2), all[i + 1]]] : a, []));
const label = args.label ?? "game.loop";
const loops = Number(args.loops ?? 50);
const syms = symbols(args.symbols ?? "build/chasehq.json");
const addr = syms[label];
if (addr === undefined) throw new Error(`no symbol ${label}`);

const s = await bootDisc(args.disc ?? "build/chasehq.ssd", args.model ?? "B-DFS1.2");
// a label in sideways RAM counts only with the code's bank paged in (its number is at &00)
const bankOf = () => (addr >= 0x8000 && addr < 0xC000 ? () => s.readMemory(0, 1)[0] : null);
if (!(await runTo(s, addr, 40000000, bankOf()))) throw new Error(`never reached ${label}`);
const times = [];
let last = s.elapsedCycles;
for (let i = 0; i < loops; i++) {
    if (!(await runTo(s, addr, 40000000, bankOf()))) throw new Error(`loop ${i}: never came back to ${label}`);
    times.push(s.elapsedCycles - last);
    last = s.elapsedCycles;
}
times.sort((a, b) => a - b);
const f = (c) => (c / 39936).toFixed(2);
const med = times[times.length >> 1];
console.log(`${label} (&${addr.toString(16).toUpperCase()}): ${loops} loops, cycles median ${med} ` +
    `(${f(med)} frames), min ${times[0]} (${f(times[0])}), max ${times[times.length - 1]} (${f(times[times.length - 1])})`);
if (args.png) {
    await s.runFrames(2);
    writeFileSync(args.png, await s.screenshotActive({ scale: 1 }));
}
s.destroy();
