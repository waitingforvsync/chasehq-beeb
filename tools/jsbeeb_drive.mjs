// Drive the game in headless jsbeeb with the real IRQ: the CPC's demo rule at the wheel (accelerate; gear at
// 150; right if X is &105 or more, left under &F6), each loop timed, screenshots at the loops asked for.
//
//   node tools/jsbeeb_drive.mjs [--loops 400] [--shots 250,300,330] [--prefix build/drive] [--right 1]
//
// (--right: X kept about &D0 instead, right of centre: a fork's right branch)
//
// Prints the loops' cycles by fifties (median, max) and the road's segment, speed and fork state.

import { writeFileSync } from "node:fs";
import { BBC, bootDisc, runTo, symbols } from "./jsbeeb.mjs";

const args = Object.fromEntries(process.argv.slice(2).reduce((a, x, i, all) =>
    x.startsWith("--") ? [...a, [x.slice(2), all[i + 1]]] : a, []));
const loops = Number(args.loops ?? 400);
const shots = new Set((args.shots ?? "").split(",").filter((x) => x).map(Number));
const prefix = args.prefix ?? "build/drive";
const syms = symbols();
const loop = syms["game.loop"];
const s = await bootDisc();
const bank = () => s.readMemory(0, 1)[0];               // (the code's bank's number, at &00)
const word = (name) => { const m = s.readMemory(syms[name], 2); return m[0] | m[1] << 8; };
const byte = (name) => s.readMemory(syms[name], 1)[0];

const held = new Set();
const hold = (key, on) => {
    if (on && !held.has(key)) { s.keyDownRaw(key); held.add(key); }
    if (!on && held.has(key)) { s.keyUpRaw(key); held.delete(key); }
};

if (!(await runTo(s, loop, 40000000, loop >= 0x8000 ? bank : null))) throw new Error("never reached the loop");
let last = s.elapsedCycles;
let times = [];
for (let i = 1; i <= loops; i++) {
    const x = word("RoadX"), speed = word("RoadSpeed"), gear = byte("CarGear");
    hold(BBC.A, true);
    hold(BBC.N, (speed >= 150) === (gear === 0));
    const [hi, lo] = args.right ? [0xD8, 0xC8] : [0x105, 0xF6];
    hold(BBC.L, x >= hi);
    hold(BBC.K, x < lo);
    if (!(await runTo(s, loop, 40000000, loop >= 0x8000 ? bank : null))) throw new Error(`loop ${i}: lost`);
    times.push(s.elapsedCycles - last);
    last = s.elapsedCycles;
    if (shots.has(i)) writeFileSync(`${prefix}${i}.png`, await s.screenshotActive({ scale: 1 }));
    if (i % 50 === 0) {
        times.sort((a, b) => a - b);
        const f = (c) => (c / 39936).toFixed(2);
        console.log(`loops ${i - 49}-${i}: median ${f(times[times.length >> 1])} frames, max ` +
            `${f(times[times.length - 1])}; seg ${byte("RoadSeg")} speed ${word("RoadSpeed")} fork seen ` +
            `${byte("ForkSeen")} sep ${word("ForkSep")} branch ${byte("ForkBranch")} DIST ` +
            `${byte("Dist") .toString(16)}/${byte("Dist") === undefined ? "" : s.readMemory(syms["Dist"] + 1, 1)[0].toString(16)}`);
        times = [];
    }
}
s.destroy();
