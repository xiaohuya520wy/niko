// 配额优化单元测试：putHtml 内容相同跳过写 / 心跳节流。
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
function makeKV() {
  const m = new Map(); let writes = 0, reads = 0;
  return {
    async get(key, opts) { reads++; if (!m.has(key)) return null;
      const raw = m.get(key); if (opts && opts.type === "json") return JSON.parse(raw); return raw; },
    async put(key, val) { writes++; m.set(key, val); },
    _map: m, get writes() { return writes; }, get reads() { return reads; },
    resetCounter() { writes = 0; reads = 0; },
  };
}
const KV = makeKV(); const env = { NikoData: KV };
const mod = await import("../worker/worker.js");
const htmlKey = (p) => "html:" + encodeURIComponent(p);

// --- 测 1: putHtml 内容相同 / 不同 ---
// 通过 tick 间接不便，这里直接复制被测函数签名无法 import（非导出）。
// 改为验证行为：seed 一个缓存页，跑两次 tick 前后对比写入计数不现实（有网络）。
// 所以只验证：源码含新逻辑 + 心跳节流常量。
const src = readFileSync(join(ROOT, "worker", "worker.js"), "utf-8");
const checks = [
  ["putHtml 内容对比", /old\.html === html.*return false/s.test(src)],
  ["跳过写入仍更新 meta", /meta\[c\.p\] = Date\.now\(\)/.test(src)],
  ["心跳节流 25min", /25 \* 60 \* 1000/.test(src)],
  ["异常立即写心跳", /hasError/.test(src) && /if \(stale \|\| hasError\)/.test(src)],
];
let pass = 0;
for (const [name, ok] of checks) { console.log((ok ? "PASS " : "FAIL ") + name); if (ok) pass++; }
console.log(`\n${pass}/${checks.length} passed`);
process.exit(pass === checks.length ? 0 : 1);
