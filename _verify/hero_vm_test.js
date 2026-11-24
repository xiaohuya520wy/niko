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

/* 2026-11-24 回归 fixture：PGL Major Singapore 2026 参赛名单写了 Falcons，
   但赛程五场全是 TBD vs TBD（对手未定）。旧逻辑因此跳过本届，
   首页错显 1 月的 PGL Bucharest 2027。 */
const tbdData = Object.assign({}, D, {
  next_match: null,
  upcoming_tournaments: [
    { id: 'pgl-2026-singapore', name: 'PGL Major Singapore 2026', short: 'PGL Major Singapore 2026',
      start: '2026-11-24T00:00:00Z', end: '2026-12-13T23:59:59Z',
      date_text: 'Nov 24 – Dec 13', tier: 'S-Tier', status: 'live' },
    { id: 'pgl-2027-bucharest', name: 'PGL Bucharest 2027', short: 'PGL Bucharest 2027',
      start: '2027-01-17T00:00:00Z', end: '2027-01-24T23:59:59Z',
      date_text: 'Jan 17–24', tier: 'S-Tier', status: 'upcoming' }
  ]
});
const tbdEv = { events: [
  { id: 'pgl-2026-singapore', name: 'PGL Major Singapore 2026', short: 'PGL Major Singapore 2026',
    tier: 'S-Tier', status: 'live', tag: 'next',
    start: '2026-11-24T00:00:00Z', end: '2026-12-13T23:59:59Z',
    date_text: 'Nov 24 – Dec 13', teams: [{ name: 'Falcons' }], brackets: [],
    schedule: [
      { a: 'TBD', b: 'TBD', ts: 1795492800, bo: 'Bo3', round: '小组赛',
        id: 'pgl-2026-singapore__tbd-tbd__1795492800', sa: null, sb: null },
      { a: 'TBD', b: 'TBD', ts: 1795496400, bo: 'Bo3', round: '小组赛',
        id: 'pgl-2026-singapore__tbd-tbd__1795496400', sa: null, sb: null }
    ] },
  { id: 'pgl-2027-bucharest', name: 'PGL Bucharest 2027', short: 'PGL Bucharest 2027',
    tier: 'S-Tier', status: 'upcoming', start: '2027-01-17T00:00:00Z',
    end: '2027-01-24T23:59:59Z', date_text: 'Jan 17–24', teams: [], brackets: [], schedule: [] }
] };

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

function simulate(iso, opt) {
  const fixed = Date.parse(iso);
  const EVx = (opt && opt.ev) || EV;
  const Dx = (opt && opt.data) || D;
  const els = { 'niko-data': makeEl('niko-data') };
  els['niko-data'].textContent = JSON.stringify(Dx);
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
  vm.runInContext('EV_FRESH = ' + JSON.stringify(EVx) + '; FRESH = ' + JSON.stringify(Dx) + '; render();', ctx);
  const hero = els.app.innerHTML;
  const pick = re => { const m = hero.match(re); return m ? m[1] : null; };
  const lf = vm.runInContext('JSON.stringify(liveFixture() && ({a:liveFixture().m.a,b:liveFixture().m.b,ts:liveFixture().ts,playing:liveFixture().playing}))', ctx);
  const stillIn = vm.runInContext("JSON.stringify(falconsStillIn({name:'PGL Major Singapore 2026'}))", ctx);
  return {
    time: iso,
    fixture: JSON.parse(lf),
    stillIn: JSON.parse(stillIn),
    hero,
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
// 期望值从数据里现算，不写死 12:30（2026-11-24 上游把该场从 12:30 改到 12:15，
// 旧断言因此误报；真正要守的是「按场次 ts 判断」而不是某个具体钟点）。
const nov11ev = (EV.events || []).find(e => /blast-rivals-2026-fall/i.test(e.id || '')
                                          || /BLAST Rivals Fall 2026/i.test(e.name || ''));
let nov11m = null;
if (nov11ev) {
  const all = [...(nov11ev.schedule || [])];
  for (const b of (nov11ev.brackets || [])) for (const rd of (b.rounds || []))
    for (const m of (rd.matches || [])) all.push(m);
  nov11m = all.find(m => {
    const an = typeof m.a === 'string' ? m.a : (m.a && m.a.name) || '';
    const bn = typeof m.b === 'string' ? m.b : (m.b && m.b.name) || '';
    return /falcon/i.test(an + ' ' + bn) && /vitality/i.test(an + ' ' + bn);
  }) || null;
}
const nov11ts = nov11m ? (nov11m.ts || parseInt(String(nov11m.id || '').split('__').pop(), 10)) : null;
const hm = ts => { const d = new Date(ts * 1000);
  return String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0'); };
const hms = sec => { const s = Math.max(0, Math.floor(sec)), p = n => String(n).padStart(2, '0');
  return Math.floor(s / 86400) + ':' + p(Math.floor(s % 86400 / 3600)) + ':' + p(Math.floor(s % 3600 / 60)) + ':' + p(s % 60); };
if (!nov11ts) console.log('  - 跳过 11-11 用例：当前数据集不含 Falcons vs Vitality');
else {
  const expOpen = hm(nov11ts);
  const expCd = hms(nov11ts - Date.parse('2026-11-11T09:57:00+08:00') / 1000);
  const r = t('09:57');
  if (r) {
    check(r.fixture && /Falcons/.test(r.fixture.a + ' ' + r.fixture.b)
      && /Vitality/.test(r.fixture.a + ' ' + r.fixture.b),
      '09:57 首页必须显示 Falcons vs Vitality');
    check(r.tag === '下一场比赛', '09:57 标签必须是「下一场比赛」，不能是「赛事进行中」');
    check(new RegExp(expOpen.replace(':', '\\:')).test(r.open || ''),
      '开赛时间必须精确到 ' + expOpen + '，不能是日期零点 08:00');
    check(r.cd === expCd, '09:57 倒计时必须是 ' + expCd + '，不能归零');
    check(r.status === '待战', 'HUD 必须是「待战」，不能是「进行中」');
  }
  if (t('10:05')) check(new RegExp(expOpen.replace(':', '\\:')).test(t('10:05').open || ''),
    '赛事首场开打后，Falcons vs Vitality 仍须留在首页');
  const pre = simulate(new Date((nov11ts - 60) * 1000).toISOString());
  const post = simulate(new Date((nov11ts + 60) * 1000).toISOString());
  check(pre.cd === '0:00:01:00', '开赛前 1 分钟倒计时必须显示 00:01:00');
  check(post.tag === '正在进行' && post.status === '进行中', '开赛后才可切换为「正在进行」');
}

console.log('\n=== 断言（防止「对手未定被当成没比赛」回归） ===');
const tb = simulate('2026-11-24T08:54:00+08:00', { data: tbdData, ev: tbdEv });
console.log('2026-11-24 08:54 |', tb.tag, '|', tb.fixture ? tb.fixture.a + ' vs ' + tb.fixture.b : '(无)',
  '| 开赛', tb.open, '| 倒计时', tb.cd, '| 仍在参赛', tb.stillIn);
check(tb.stillIn === true, '参赛名单有 Falcons 时不得判定为「已出局」');
check(tb.fixture && tb.fixture.a === 'Falcons' && tb.fixture.b === 'TBD',
  '对手未定的比赛必须进入首页（Falcons vs 待定），不能当成没比赛');
check(/PGL Major Singapore 2026/.test(tb.hero || ''),
  '首页必须显示 PGL Major Singapore 2026');
check(/12:00/.test(tb.open || ''), '倒计时目标必须是新加坡首场 12:00，不能跳到 1 月');
check(tb.cd === '0:03:06:00', '08:54 距 12:00 应为 3 小时 6 分');
console.log(failed ? `\nREGRESSION FAILED (${failed})` : '\nALL PASS');
process.exit(failed ? 1 : 0);
