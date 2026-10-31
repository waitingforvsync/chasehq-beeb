// Headless jsbeeb for the tools (as Teddy Boy's): jsbeeb itself, the build's symbols, and the game booted
// from its disc.
//
// jsbeeb comes from jsbeeb-mcp's npm package (npx jsbeeb-mcp fetches it), or JSBEEB=path/to/jsbeeb.

import { existsSync, readFileSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

function jsbeebSrc() {
    if (process.env.JSBEEB) return join(process.env.JSBEEB, "src");
    const npx = join(homedir(), ".npm", "_npx");
    for (const d of existsSync(npx) ? readdirSync(npx) : []) {
        const src = join(npx, d, "node_modules", "jsbeeb", "src");
        if (existsSync(join(src, "machine-session.js"))) return src;
    }
    throw new Error("jsbeeb not found: run `npx jsbeeb-mcp` once, or set JSBEEB");
}

const src = jsbeebSrc();
const { MachineSession } = await import(join(src, "machine-session.js"));
export const { BBC } = await import(join(src, "keymap.js"));

// every symbol in the build: labels, ZA_AUTOs and assignments, scoped names as Baron writes them
export function symbols(path = "build/chasehq.json") {
    const syms = {};
    for (const asm of JSON.parse(readFileSync(path)).assemblies)
        for (const section of asm.sections)
            for (const kind of ["labels", "za_autos", "assignments"])
                for (const [k, v] of Object.entries(section[kind] || {})) syms[k] = typeof v === "object" ? v.value : v;
    return syms;
}

// A Model B with DFS (the 8271's DFS 1.2, or a jsbeeb model named), the disc booted with SHIFT-BREAK
export async function bootDisc(disc = "build/chasehq.ssd", model = "B-DFS1.2") {
    const s = new MachineSession(model, { discImage: disc });
    await s.initialise();
    await s.boot();
    s.keyDownRaw(BBC.SHIFT);
    s.reset(true);
    await s.runFor(2000000);
    s.keyUpRaw(BBC.SHIFT);
    return s;
}

// the sideways RAM bank paged in: ROMSEL as jsbeeb has it
export const paged = (s) => s._machine.processor.romsel & 15;

// Run until PC is addr (off it first, if it's there already), up to maxCycles; with bank (a function giving
// a bank's number), only an arrival while that bank's paged in counts (a bank address is in both banks).
// True if it got there.
export async function runTo(s, addr, maxCycles = 40000000, bank = null) {
    if (s.registers().pc === addr) await s.runFor(1);   // off it first
    const id = s.addBreakpoint("execute", addr);
    let hit = false;
    try {
        for (let left = maxCycles; left > 0 && !hit; left -= 400000) {
            s.resetBreakpointHits();
            await s.runFor(400000);
            hit = s.hitBreakpoint() !== null && s.registers().pc === addr && (bank === null || paged(s) === bank());
            if (s.hitBreakpoint() !== null && !hit && s.registers().pc === addr) await s.runFor(1);
        }
    } finally {
        s.removeBreakpoint(id);
    }
    return hit;
}
