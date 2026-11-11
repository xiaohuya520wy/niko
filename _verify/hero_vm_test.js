/* 用真实线上数据 + 真实 index.html 脚本，模拟不同时刻的首页 hero 渲染。
   验证 2026-11-11 修复：比赛时间精确到分钟，12:30 的 Falcons 比赛不会被日期零点过滤。 */
process.env.TZ = 'Asia/Shanghai';
const fs = require('fs');
const vm = require('vm');
const path = require('path');
const ROOT = path.join(__dirname, '..');
// 默认用本地构建产物；设 HERO_HTML / HERO_DATA / HERO_EV 可对线上页面跑同一套断言
const htmlPath = process.env.HERO_HTML || path.join(ROOT, 'index.html');
const dataPath = process.env.HERO_DATA || path.join(ROOT, 'data.json');
const evPath = process.env.HERO_EV || path.join(ROOT, 'event.json');
const html = fs.readFileSync(htmlPath, 'utf8');
const scripts = html.match(/<script>([\s\S]*?)<\/script>/g) || [];
const js = scripts[scripts.length - 1].replace(/^<script>/, '').replace(/<\/script>$/, '')
  .replace(/render\(\);\s*boot\(\);\s*$/, '');
const D = JSON.parse(fs.readFileSync(dataPath, 'utf8'));
const EV = JSON.parse(fs.readFileSync(evPath, 'utf8'));
const localD = D;

function makeEl(id) {
  return {
    id, innerHTML: '', textContent: '', value: '', style: {}, dataset: {}, children: [],
    classList: { add() {}, remove() {}, toggle() {}, contains() { return false; } },
    onclick: null, oninput: null,
    addEventListener() {}, removeEventListener() {},
    querySelectorAll() { return []; }, querySelector() { return null; },
    getAttribute() { return null; }, setAttribute() {}, appendChild() {}, removeChild() {},
    scrollTo() {}, focus() {}, click() {},
    getBoundingClientRect() { return { width: 0, height: 0, left: 0, top: 0 }; }
  };
}

function simulate(iso) {
  const fixed = Date.parse(iso);
  const els = { 'niko-data': makeEl('niko-data') };
  els['niko-data'].textContent = JSON.stringify(localD);
  const document = {
    getElementById(id) { return els[id] || (els[id] = makeEl(id)); },
    querySelectorAll() { return []; }, querySelector() { return null; },
    createElement(t) { return makeEl(t); },
    body: makeEl('body'), documentElement: makeEl('html'), addEventListener() {}
  };
  class FakeDate extends Date {
    constructor(...a) { if (a.length) super(...a); else super(fixed); }
    static now() { return fixed; }
  }
  const ctx = vm.createContext({
    document, console, URLSearchParams, Date: FakeDate, Math, JSON, Intl, Promise, Map, Set,
    String, Number, Array, Object, Boolean, RegExp, Error, TypeError,
    parseInt, parseFloat, isNaN, encodeURIComponent, decodeURIComponent,
    window: { scrollTo() {}, addEventListener() {}, matchMedia: () => ({ matches: false, addListener() {} }) },
    matchMedia: () => ({ matches: false, addListener() {}, addEventListener() {} }),
    location: { search: '', pathname: '/index.html', href: 'https://niko-8u7.pages.dev/' },
    history: { replaceState() {} }, navigator: { userAgent: 'node' },
    setTimeout: () => 0, clearTimeout() {}, setInterval: () => 0, clearInterval() {},
    requestAnimationFrame: () => 0, fetch: () => Promise.reject(new Error('offline'))
  });
  vm.runInContext(js, ctx);
  vm.runInContext('EV_FRESH = ' + JSON.stringify(EV) + '; FRESH = ' + JSON.stringify(D) + '; render();', ctx);
  const hero = els.app.innerHTML;
  const pick = re => { const m = hero.match(re); return m ? m[1] : null; };
  const lf = vm.runInContext('JSON.stringify(liveFixture() && ({a:liveFixture().m.a,b:liveFixture().m.b,ts:liveFixture().ts,playing:liveFixture().playing}))', ctx);
  return {
    time: iso,
    fixture: JSON.parse(lf),
    tag: pick(/<span class="tag">([^<]*)<\/span>/),
    open: pick(/开赛（北京时间）：([^<]*)</),
    note: pick(/<div class="hero-note">([^<]*)</),
    cd: ['cdD', 'cdH', 'cdM', 'cdS'].map(k => els[k] ? els[k].textContent : '?').join(':'),
    status: els.statusTxt ? els.statusTxt.textContent : '?',
    hasFalcons: /Falcons/.test(hero),
    hasVitality: /Vitality/.test(hero),
    heroLen: hero.length
  };
}

const cases = [
  '2026-11-11T09:57:00+08:00',   // 用户截图时刻：12:30 才开打
  '2026-11-11T10:05:00+08:00',   // 赛事首场 10:00 已开打，Falcons 场未开
  '2026-11-11T12:29:00+08:00',   // 开赛前 1 分钟
  '2026-11-11T12:31:00+08:00',   // 开赛后 1 分钟
  '2026-11-11T16:00:00+08:00'    // 3.2 小时直播窗口之后
];
const by = {};
let failed = 0;
for (const c of cases) {
  try {
    const r = simulate(c); by[c] = r;
    console.log(c, '|', r.tag, '|', r.fixture ? r.fixture.a + ' vs ' + r.fixture.b : '(无)',
      '| 开赛', r.open, '| 倒计时', r.cd, '| HUD', r.status);
  } catch (e) { console.log(c, 'ERROR', e.message); failed++; }
}
function check(cond, msg) { if (!cond) { console.log('  ✗ FAIL:', msg); failed++; } else console.log('  ✓', msg); }
console.log('\n=== 断言（防止「按日期零点误判开赛」回归） ===');
const t = k => by['2026-11-11T' + k + ':00+08:00'];
if (t('09:57')) {
  const r = t('09:57');
  check(r.fixture && r.fixture.a === 'Vitality' && r.fixture.b === 'Falcons',
    '09:57 首页必须显示 12:30 的 Vitality vs Falcons');
  check(r.tag === '下一场比赛', '09:57 标签必须是「下一场比赛」，不能是「赛事进行中」');
  check(/12:30/.test(r.open || ''), '开赛时间必须精确到 12:30，不能是 08:00');
  check(r.cd === '0:02:33:00', '倒计时必须是 2 小时 33 分，不能归零');
  check(r.status === '待战', 'HUD 必须是「待战」，不能是「进行中」');
}
if (t('10:05')) check(t('10:05').fixture && /12:30/.test(t('10:05').open || ''),
  '赛事首场 10:00 开打后，12:30 的 Falcons 比赛仍须留在首页');
if (t('12:29')) check(t('12:29').cd === '0:00:01:00', '开赛前 1 分钟倒计时必须显示 00:01:00');
if (t('12:31')) check(t('12:31').tag === '正在进行' && t('12:31').status === '进行中',
  '开赛后才可切换为「正在进行」');
console.log(failed ? `\nREGRESSION FAILED (${failed})` : '\nALL PASS');
process.exit(failed ? 1 : 0);
