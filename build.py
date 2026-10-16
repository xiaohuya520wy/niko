"""生成 NiKo 赛事跟踪站：一级页 + 三个二级页（比赛详情 / 队伍 / 选手）。

所有页面内联 data.json，离线可直接打开；联网时会尝试拉取更新后的 data.json 覆盖。
"""
import json
import pathlib

ROOT = pathlib.Path(__file__).parent
DATA = json.loads((ROOT / "data.json").read_text(encoding="utf-8"))
_gh = ROOT / "github"
REPO = (ROOT / "repo.txt").read_text(encoding="utf-8").strip() or "__REPO__"

# 真实地图背景（由 make_map_bg.py 产出：地图名 -> {f: 图片路径, l: LQIP data URI}）
MAP_BG = {}
try:
    MAP_BG = json.loads((ROOT / "assets" / "maps" / "index.json").read_text(encoding="utf-8"))
except Exception:
    pass

# 赛事中心数据（由 fetch_event.py 产出）
EVENT_DATA = {}
try:
    EVENT_DATA = json.loads((ROOT / "event.json").read_text(encoding="utf-8"))
except Exception:
    pass

# 官方照片墙（由 fetch_photos.py 产出：按年份倒序的官方照片清单）
PHOTOS = []
try:
    PHOTOS = json.loads((ROOT / "photos.json").read_text(encoding="utf-8"))
except Exception:
    pass

CSS = r"""/* ========== NiKo 赛事跟踪 · 视觉升级（正规 + 设计感）========== */
:root{
  --bg:#ECEAF8;
  --bg2:#E3E0F5;
  --panel:#FFFFFF;
  --panel2:#F5F4FE;
  --panel3:#E8E6F8;
  --line:#E7E5F7;
  --line-soft:#D8D5F0;
  --hi:#FFFFFF;
  --shadow-c:transparent;
  --ink:#242A52;
  --ink2:#6B7099;
  --dim:#A0A4C6;
  --amber:#5B5CE6;
  --amber2:#8B5CF6;
  --amber-bg:#ECEAFE;
  --cyan:#1FB6C9;
  --xh:#00FF91;            /* NiKo 准星自定义绿（游戏内实际颜色 rgb 0,255,145）*/
  --win:#15B981;
  --win-bg:#DCF6EC;
  --loss:#F0566E;
  --loss-bg:#FDE6EA;
  --ct:#4C7FD9;
  --t:#F0904A;
  --exp:#9C6BEB;
  --grad:linear-gradient(120deg,#5B5CE6 0%,#8B5CF6 46%,#1FB6C9 100%);
  --grad-num:linear-gradient(180deg,#4F46E5 0%,#7C3AED 55%,#0EA5B7 100%);
  --grad-soft:linear-gradient(120deg,#ECEAFE,#F4EAFD 58%,#E2F6F9);
  --glow:0 26px 56px -24px rgba(91,92,230,.55);
  --shadow-lg:0 26px 54px -26px rgba(66,68,158,.36);
  --shadow-md:0 14px 30px -16px rgba(66,68,158,.28);
  --shadow-sm:0 7px 18px -9px rgba(66,68,158,.18);
  --sans:"Noto Sans SC","PingFang SC","HarmonyOS Sans SC","Microsoft YaHei",system-ui,sans-serif;
  --display:"Noto Serif SC","Songti SC",serif;
  --mono:"Rajdhani","Noto Sans SC","SF Mono",Consolas,"Courier New",monospace;
  --tech:"Rajdhani","Noto Sans SC",system-ui,sans-serif;
}
*{box-sizing:border-box;margin:0;padding:0;-webkit-tap-highlight-color:transparent}
img{display:block}
body{
  background-color:var(--bg);
  background-image:
    radial-gradient(1100px 520px at 88% -12%, #E9E3FE 0%, transparent 60%),
    radial-gradient(900px 460px at -12% 4%, #E6F6F8 0%, transparent 58%),
    radial-gradient(circle at 1px 1px, rgba(36,42,82,.05) 1px, transparent 0);
  background-size:auto,auto,22px 22px;
  background-attachment:fixed;
  color:var(--ink);
  font-family:var(--sans);
  font-size:16px;
  line-height:1.72;
  min-height:100vh;
  text-rendering:optimizeLegibility;
  -webkit-font-smoothing:antialiased;
}
a{color:inherit;text-decoration:none}
.wrap{max-width:780px;margin:0 auto;padding:0 16px 88px}

/* === 顶栏 === */
.hud{position:sticky;top:0;z-index:50;
  background:rgba(255,255,255,.78);
  backdrop-filter:blur(16px) saturate(140%);-webkit-backdrop-filter:blur(16px) saturate(140%);
  border-top:3px solid transparent;border-image:var(--grad) 1;
  box-shadow:0 1px 0 var(--line)}
.hud-in{max-width:780px;margin:0 auto;padding:12px 16px;display:flex;align-items:center;gap:12px}
.brand{display:flex;flex-direction:column;line-height:1.12}
.brand b{font-family:var(--tech);font-size:25px;letter-spacing:.2em;font-weight:700;
  background:var(--grad);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;color:var(--amber)}
.brand small{font-family:var(--tech);font-size:10px;color:#fff;letter-spacing:.32em;font-weight:600;
  background:var(--grad);padding:3px 10px;margin-top:4px;border-radius:999px;display:inline-block;width:fit-content}
.hud .ava{width:38px;height:38px;flex:none;border-radius:13px}
.status{margin-left:auto;display:flex;align-items:center;gap:8px;
  font-family:var(--mono);font-size:12px;letter-spacing:.1em;font-weight:600;
  background:var(--panel2);color:var(--ink);
  border:1px solid var(--line);padding:7px 13px;border-radius:999px;box-shadow:var(--shadow-sm)}
.dot{width:8px;height:8px;border-radius:50%;background:var(--amber)}
.dot.live{background:var(--loss);animation:pulse 1.2s infinite}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.4;transform:scale(.7)}}

/* === 准星品牌图标 === */
.crosshair{width:36px;height:36px;flex:none;position:relative;
  background:var(--grad);border-radius:12px;box-shadow:0 8px 18px -7px rgba(91,92,230,.6)}
.crosshair::before,.crosshair::after{content:"";position:absolute;background:#fff;border-radius:2px}
.crosshair::before{left:50%;top:8px;width:3px;height:19px;transform:translateX(-50%)}
.crosshair::after{top:50%;left:8px;height:3px;width:19px;transform:translateY(-50%)}
.crosshair span{display:none}

/* === 头像 === */
.av{background:var(--panel2);border:1px solid var(--line);object-fit:cover;flex:none;display:block;border-radius:16px;
  box-shadow:0 0 0 2px #fff,0 0 0 4px var(--line)}
.av-xl{width:84px;height:84px}
.av-lg{width:66px;height:66px}
.av-ph{display:grid;place-items:center;font-family:var(--tech);font-weight:700;color:var(--amber);
  background:var(--grad-soft);border:1px solid var(--line);flex:none;border-radius:16px;
  box-shadow:0 0 0 2px #fff,0 0 0 4px var(--line)}
.av-ph-xl{width:84px;height:84px;font-size:24px}
.av-ph-lg{width:66px;height:66px;font-size:20px}

.prof{display:flex;align-items:center;gap:16px;background:linear-gradient(180deg,#fff,#FBFAFF);
  border:1px solid var(--line);border-radius:24px;padding:18px 20px;margin-top:18px;
  box-shadow:var(--shadow-md);position:relative;overflow:hidden}
.prof::before{content:"";position:absolute;left:0;top:14px;bottom:14px;width:5px;border-radius:3px;background:var(--grad)}
.prof .nick{font-family:var(--tech);font-size:27px;font-weight:700;letter-spacing:.04em;color:var(--ink);padding-left:6px}
.prof .full{font-family:var(--mono);font-size:13px;color:var(--ink2);margin-top:3px;letter-spacing:.04em;padding-left:6px}
.prof .meta{font-family:var(--mono);font-size:11px;color:var(--amber);margin-top:8px;letter-spacing:.06em;
  background:var(--amber-bg);padding:4px 11px;display:inline-block;border-radius:999px;font-weight:600;padding-left:11px}
.prof-link{margin-left:auto;font-family:var(--mono);font-size:12px;color:var(--amber);font-weight:600;
  background:var(--amber-bg);padding:7px 13px;border-radius:999px;letter-spacing:.08em;white-space:nowrap}

/* === 队友横滑 === */
.scroller{display:flex;gap:12px;overflow-x:auto;padding:4px 2px 12px;scroll-snap-type:x mandatory;
  -webkit-overflow-scrolling:touch;scrollbar-width:none}
.scroller::-webkit-scrollbar{display:none}
.pc{flex:0 0 136px;scroll-snap-align:start;background:var(--panel);
  border:1px solid var(--line);border-radius:20px;padding:15px 10px;text-align:center;
  box-shadow:var(--shadow-sm);position:relative;overflow:hidden}
.pc::before{content:"";position:absolute;top:0;left:0;right:0;height:4px;background:var(--grad);opacity:.85}
.pc:active{transform:scale(.97)}
.pc .ph{width:64px;height:64px;margin:0 auto 11px}
.pc .ph .av,.pc .ph .av-ph{border-radius:16px}
.pc .pid{font-size:16px;font-weight:700;letter-spacing:.02em;white-space:nowrap;
  overflow:hidden;text-overflow:ellipsis;color:var(--ink)}
.pc .prole{font-family:var(--mono);font-size:10px;color:var(--amber);background:var(--amber-bg);
  padding:3px 9px;display:inline-block;margin-top:6px;letter-spacing:.08em;border-radius:999px;font-weight:600}
.pc .pnat{font-family:var(--mono);font-size:11px;color:var(--ink2);margin-top:5px;letter-spacing:.06em}
.hint{font-family:var(--mono);font-size:11px;color:var(--dim);letter-spacing:.16em;margin-bottom:7px;text-transform:uppercase}

/* === 章节 === */
.sec{margin-top:36px;position:relative}
.sec-h{display:flex;align-items:center;gap:12px;margin-bottom:15px}
.sec-h b{font-family:var(--display);font-size:19px;font-weight:700;color:var(--ink);letter-spacing:.04em;
  position:relative;padding-left:15px}
.sec-h b::before{content:"";position:absolute;left:0;top:.2em;bottom:.2em;width:5px;border-radius:3px;background:var(--grad)}
.sec-h i{flex:1;height:1px;background:linear-gradient(90deg,var(--line-soft),transparent)}
.sec-h em{font-family:var(--mono);font-size:12px;color:var(--amber);font-style:normal;letter-spacing:.14em;font-weight:600}
.sec-h a em{color:var(--amber);font-weight:700}

/* === 下一场比赛 hero（深色渐变焦点）=== */
.hero{margin-top:18px;position:relative;border-radius:28px;overflow:hidden;
  background:linear-gradient(135deg,#4738C8 0%,#6B49D6 44%,#1F9FB4 115%);
  box-shadow:var(--glow);border:1px solid rgba(255,255,255,.18);color:#fff}
.hero::before{content:"";position:absolute;inset:0;pointer-events:none;mix-blend-mode:overlay;
  background:
    radial-gradient(120% 80% at 85% 0%, rgba(255,255,255,.22), transparent 55%),
    repeating-linear-gradient(135deg, rgba(255,255,255,.06) 0 2px, transparent 2px 13px)}
.hero::after{content:"";position:absolute;right:-40px;bottom:-30px;width:260px;height:200px;
  background:radial-gradient(closest-side,rgba(255,255,255,.22),transparent);pointer-events:none}
.hero-top{display:flex;align-items:center;gap:9px;padding:16px 20px 0;position:relative;z-index:1}
.tag{font-family:var(--mono);font-size:11px;letter-spacing:.2em;color:#fff;font-weight:600;
  background:rgba(255,255,255,.16);padding:5px 13px;border-radius:999px;backdrop-filter:blur(4px)}
.hero-body{padding:20px 16px 24px;text-align:center;position:relative;z-index:1}
.vs{display:flex;align-items:center;justify-content:center;gap:16px;margin:8px 0 4px;flex-wrap:wrap}
.team{font-size:32px;font-weight:700;letter-spacing:.03em;color:#fff;font-family:var(--tech);
  text-shadow:0 2px 16px rgba(0,0,0,.28)}
.team.tbd{color:rgba(255,255,255,.62)}
/* 下一场比赛：双方队标 + 队名 */
.hero-team{display:flex;flex-direction:column;align-items:center;gap:9px;width:104px}
.hero-team img{width:66px;height:66px;object-fit:contain;filter:drop-shadow(0 5px 16px rgba(0,0,0,.34))}
.hero-logo-ph{width:66px;height:66px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-style:normal;font-family:var(--tech);font-size:22px;font-weight:700;color:#fff;
  background:rgba(255,255,255,.18);border:1px solid rgba(255,255,255,.3)}
.hero-team b{font-family:var(--tech);font-size:17px;font-weight:700;line-height:1.25;letter-spacing:.01em;
  color:#fff;text-shadow:0 2px 16px rgba(0,0,0,.3);text-align:center}
.vs-mid{font-family:var(--mono);font-size:14px;color:#fff;font-weight:600;letter-spacing:.1em;
  background:rgba(255,255,255,.18);padding:5px 13px;border-radius:999px;backdrop-filter:blur(4px)}
.hero-sub{font-family:var(--mono);font-size:13px;color:rgba(255,255,255,.85);letter-spacing:.06em}
.hero-note{font-family:var(--mono);font-size:12px;color:#fff;letter-spacing:.05em;margin-top:12px;
  background:rgba(255,255,255,.16);padding:5px 13px;display:inline-block;border-radius:999px;backdrop-filter:blur(4px)}

/* === 倒计时 === */
.cd{display:grid;grid-template-columns:repeat(4,1fr);gap:11px;margin:22px 0 6px}
.cd div{background:var(--grad-soft);border:1px solid var(--line);border-radius:20px;padding:16px 4px 14px;
  box-shadow:inset 0 1px 0 #fff;position:relative;overflow:hidden}
.cd div::before{content:"";position:absolute;top:0;left:0;right:0;height:3px;background:var(--grad);opacity:.8}
.cd b{display:block;font-family:var(--tech);font-size:42px;font-weight:700;
  background:var(--grad-num);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;color:var(--amber);
  font-variant-numeric:tabular-nums;font-feature-settings:"tnum";line-height:1}
.cd span{font-family:var(--mono);font-size:10px;color:var(--ink2);letter-spacing:.34em;margin-top:8px;display:block;text-transform:uppercase}

/* === 未来赛程卡 === */
.up{display:grid;gap:13px;grid-template-columns:repeat(auto-fit,minmax(220px,1fr))}
.up-c{background:var(--panel);border:1px solid var(--line);border-radius:20px;padding:16px 18px;position:relative;
  box-shadow:var(--shadow-sm);overflow:hidden}
.up-c::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--grad);opacity:.85}
.up-c .n{font-size:17px;font-weight:700;letter-spacing:.01em;color:var(--ink);padding-right:64px}
.up-c .d{font-family:var(--mono);font-size:13px;color:var(--amber);margin-top:5px;font-weight:600;letter-spacing:.04em}
.up-c .m{font-family:var(--mono);font-size:12px;color:var(--ink2);margin-top:9px;letter-spacing:.04em}
.tier{position:absolute;top:14px;right:14px;font-family:var(--mono);font-size:10px;text-transform:uppercase;
  color:var(--amber);background:var(--amber-bg);padding:4px 10px;letter-spacing:.08em;font-weight:600;border-radius:999px}

/* === 战绩 rows === */
.rows{display:flex;flex-direction:column;gap:11px}
.row{display:flex;align-items:center;gap:13px;background:var(--panel);
  border:1px solid var(--line);border-left:4px solid var(--line-soft);border-radius:18px;padding:13px 15px;
  box-shadow:var(--shadow-sm)}
.row:active{transform:scale(.985)}
.row.W{border-left-color:var(--win)}
.row.L{border-left-color:var(--loss)}
.res{width:32px;height:32px;flex:none;display:grid;place-items:center;font-family:var(--mono);
  font-size:13px;font-weight:700;color:#fff;border-radius:11px}
.res.W{background:var(--win)} .res.L{background:var(--loss)}
.sc{font-family:var(--tech);font-size:19px;font-weight:700;font-variant-numeric:tabular-nums;flex:none;width:60px;color:var(--ink);letter-spacing:.02em}
.info{flex:1;min-width:0}
.info .o{font-size:16px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--ink)}
.info .e{font-family:var(--mono);font-size:12px;color:var(--ink2);margin-top:3px;letter-spacing:.04em}
.rt{flex:none;text-align:right;font-family:var(--mono)}
.rt b{font-size:15px;color:var(--ink);font-weight:700}
.rt small{display:block;font-size:11px;color:var(--ink2);letter-spacing:.05em}
.bar{width:58px;height:7px;background:var(--panel3);margin-top:6px;margin-left:auto;border-radius:999px;overflow:hidden}
.bar i{display:block;height:100%;background:var(--grad);border-radius:999px}
.chev{flex:none;color:var(--dim);font-size:19px}
.more{display:block;width:100%;margin-top:11px;background:var(--panel);
  border:1px solid var(--line);color:var(--amber);font-family:var(--mono);font-size:13px;letter-spacing:.14em;font-weight:600;
  padding:13px;border-radius:16px;cursor:pointer;box-shadow:var(--shadow-sm)}
.more:active{transform:scale(.985)}

/* === 数据统计 === */
.grid{display:grid;gap:11px;grid-template-columns:repeat(auto-fit,minmax(112px,1fr))}
.st{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:16px 17px;
  box-shadow:var(--shadow-sm);position:relative;overflow:hidden}
.st::before{content:"";position:absolute;top:0;left:0;right:0;height:3px;background:var(--grad);opacity:.8}
.st span{display:block;font-family:var(--mono);font-size:11px;color:var(--ink2);letter-spacing:.12em;text-transform:uppercase}
.st b{display:block;font-family:var(--tech);font-size:30px;font-weight:700;margin-top:7px;
  background:var(--grad-num);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;color:var(--amber);
  font-variant-numeric:tabular-nums;line-height:1}
.st.hl b{background:none;-webkit-text-fill-color:var(--win);color:var(--win)}
.st-sub{font-family:var(--mono);font-size:12px;color:var(--ink2);margin-top:4px;letter-spacing:.04em}

/* === 战绩总览仪表盘（近一年战绩） === */
.yb{background:var(--panel);border:1px solid var(--line);border-radius:20px;padding:17px;
  box-shadow:var(--shadow-sm);position:relative;overflow:hidden}
.yb::before{content:"";position:absolute;top:0;left:0;right:0;height:3px;background:var(--grad);opacity:.85}
.yb-nums{display:flex;align-items:flex-end;gap:10px}
.yb-n{flex:none;min-width:62px}
.yb-n b{display:block;font-family:var(--tech);font-size:34px;font-weight:700;line-height:1;
  font-variant-numeric:tabular-nums}
.yb-n span{display:block;font-family:var(--mono);font-size:11px;color:var(--ink2);
  letter-spacing:.12em;margin-top:5px}
.yb-n.w b{color:var(--win)}
.yb-n.l b{color:var(--loss)}
.yb-rate{margin-left:auto;text-align:right}
.yb-rate b{display:block;font-family:var(--tech);font-size:34px;font-weight:700;line-height:1;
  font-variant-numeric:tabular-nums;background:var(--grad-num);-webkit-background-clip:text;
  background-clip:text;-webkit-text-fill-color:transparent;color:var(--amber)}
.yb-rate span{display:block;font-family:var(--mono);font-size:11px;color:var(--ink2);
  letter-spacing:.12em;margin-top:5px}
.yb-bar{position:relative;height:9px;border-radius:999px;background:var(--loss-bg);margin-top:15px}
.yb-bar i{display:block;height:100%;border-radius:999px;
  background:linear-gradient(90deg,#15B981,#1FB6C9)}
.yb-bar u{position:absolute;top:-3px;width:2px;height:15px;background:var(--ink);
  border-radius:2px;opacity:.55}
.yb-legend{display:flex;justify-content:space-between;font-family:var(--mono);font-size:11px;
  color:var(--ink2);margin-top:7px;letter-spacing:.05em}
.yb-sub{display:flex;flex-wrap:wrap;gap:6px;margin-top:13px}
.yb-tag{font-family:var(--mono);font-size:11px;color:var(--ink2);background:var(--panel2);
  border:1px solid var(--line);border-radius:999px;padding:4px 10px;letter-spacing:.04em}
.yb-tag b{color:var(--ink);font-weight:700}
.yb-blk{margin-top:15px;padding-top:13px;border-top:1px dashed var(--line-soft)}
.yb-h{display:flex;align-items:baseline;gap:8px;margin-bottom:9px}
.yb-h b{font-size:14px;color:var(--ink)}
.yb-h em{font-family:var(--mono);font-size:11px;color:var(--ink2);font-style:normal;letter-spacing:.05em}
.yb-form{display:flex;gap:5px}
.ff{flex:1;height:27px;border-radius:7px;display:grid;place-items:center;cursor:pointer;
  font-family:var(--mono);font-size:10px;font-weight:700;color:#fff;transition:transform .16s}
.ff.W{background:linear-gradient(180deg,#19C48C,#0E9C6B);box-shadow:0 5px 12px -7px rgba(21,185,129,.9)}
.ff.L{background:linear-gradient(180deg,#F2687E,#DC3E57);box-shadow:0 5px 12px -7px rgba(240,86,110,.9)}
.ff:active{transform:scale(.88)}
.yb-form-x{display:flex;gap:5px;margin-top:6px}
.yb-form-x span{flex:1;text-align:center;font-family:var(--mono);font-size:9px;color:var(--dim)}
.yk{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-top:13px}
.yk-i{background:var(--panel2);border:1px solid var(--line);border-radius:14px;padding:11px 8px;text-align:center}
.yk-i b{display:block;font-family:var(--tech);font-size:21px;font-weight:700;color:var(--ink);
  font-variant-numeric:tabular-nums;line-height:1}
.yk-i b.w{color:var(--win)} .yk-i b.l{color:var(--loss)}
.yk-i span{display:block;font-family:var(--mono);font-size:10px;color:var(--ink2);
  margin-top:5px;letter-spacing:.04em}
.yb-mon{display:flex;align-items:flex-end;gap:4px;height:62px}
.yb-mon .mo{flex:1;display:flex;flex-direction:column;justify-content:flex-end;height:100%;
  background:var(--panel2);border-radius:5px;overflow:hidden}
.yb-mon .mo i{display:block;width:100%}
.yb-mon .mo i.w{background:linear-gradient(180deg,#19C48C,#0E9C6B)}
.yb-mon .mo i.l{background:linear-gradient(180deg,#F2687E,#DC3E57)}
.yb-mon-x{display:flex;gap:4px;margin-top:5px}
.yb-mon-x span{flex:1;text-align:center;font-family:var(--mono);font-size:9px;color:var(--dim)}

/* === 地图池胜率榜 === */
.pool{margin-top:6px}
.pool-row{display:flex;align-items:center;gap:10px;padding:9px 0;
  border-bottom:1px dashed var(--line-soft)}
.pool-row:last-child{border-bottom:none}
.pool-n{flex:none;width:60px;font-family:var(--mono);font-size:12px;font-weight:600;color:var(--ink)}
.pool-b{flex:1;height:8px;background:var(--panel3);border-radius:999px;overflow:hidden}
.pool-b i{display:block;height:100%;border-radius:999px;background:var(--grad)}
.pool-v{flex:none;width:76px;text-align:right;font-family:var(--mono);font-size:11px;color:var(--ink2)}
.pool-v b{color:var(--ink);font-weight:700}

/* === 分站战绩横滑 === */
.eboard{display:flex;gap:10px;overflow-x:auto;padding-bottom:5px;margin-top:12px;
  scroll-snap-type:x mandatory;-webkit-overflow-scrolling:touch}
.eb{flex:0 0 auto;width:134px;background:var(--panel);border:1px solid var(--line);
  border-radius:16px;padding:12px;box-shadow:var(--shadow-sm);scroll-snap-align:start}
.eb .et{font-size:13px;font-weight:700;color:var(--ink);line-height:1.35;height:35px;overflow:hidden}
.eb .er{display:flex;align-items:baseline;gap:6px;margin-top:7px}
.eb .er b{font-family:var(--tech);font-size:20px;font-weight:700;color:var(--ink);
  font-variant-numeric:tabular-nums;line-height:1}
.eb .er em{font-family:var(--mono);font-size:11px;color:var(--ink2);font-style:normal}
.eb .ebar{height:6px;border-radius:999px;background:var(--panel3);margin-top:9px;overflow:hidden}
.eb .ebar i{display:block;height:100%;border-radius:999px;
  background:linear-gradient(90deg,#15B981,#1FB6C9)}
.eb .ebar i.low{background:linear-gradient(90deg,#F0904A,#F0566E)}

/* === 资料表 === */
.kv{background:var(--panel);border:1px solid var(--line);border-radius:20px;
  box-shadow:var(--shadow-sm);overflow:hidden}
.kv-row{display:flex;gap:12px;padding:12px 17px;border-bottom:1px dashed var(--line-soft);font-size:15px}
.kv-row:last-child{border-bottom:none}
.kv-row span{flex:none;width:96px;font-family:var(--mono);font-size:12px;color:var(--ink2);
  letter-spacing:.06em;padding-top:3px;font-weight:600;text-transform:uppercase}
.kv-row b{font-weight:500;color:var(--ink)}

/* === 比赛地图 === */
.map{background:var(--panel);border:1px solid var(--line);border-left:4px solid var(--line-soft);
  border-radius:18px;padding:14px 16px;margin-bottom:11px;box-shadow:var(--shadow-sm);position:relative;overflow:hidden}
.map.W{border-left-color:var(--win)} .map.L{border-left-color:var(--loss)}
.map.veto{border-left-color:var(--line-soft);opacity:.55}
.map-h{display:flex;align-items:baseline;gap:9px;margin-bottom:9px;flex-wrap:wrap}
.map-h b{font-size:17px;letter-spacing:.02em;color:var(--ink);font-weight:700}
.map-h em{font-family:var(--mono);font-size:10px;font-style:normal;color:var(--ink2);letter-spacing:.08em;
  background:var(--panel2);padding:3px 9px;border-radius:999px}
.map-en{font-family:var(--mono);font-size:11px;color:var(--dim);margin-left:7px;letter-spacing:.05em}
.map-res{margin-left:auto;font-family:var(--mono);font-size:12px;letter-spacing:.08em;font-weight:600;
  padding:4px 11px;border-radius:999px}
.map-res.W{color:#fff;background:var(--win)} .map-res.L{color:#fff;background:var(--loss)}
.mline{display:flex;align-items:center;gap:10px;margin-top:6px}
.mline .who{font-family:var(--mono);font-size:12px;color:var(--ink2);flex:none;width:62px;letter-spacing:.04em;font-weight:600}
.mline .rounds{font-family:var(--tech);font-size:19px;font-weight:700;flex:none;width:42px;
  text-align:right;font-variant-numeric:tabular-nums;color:var(--ink)}
.mline .halves{font-family:var(--mono);font-size:11px;color:var(--ink2);flex:none;width:76px}
.mline .tbar{flex:1;height:7px;background:var(--panel3);border-radius:999px;overflow:hidden}
.mline .tbar i{display:block;height:100%;background:linear-gradient(90deg,var(--win),#3ED48C);border-radius:999px}
.mline.L .tbar i{background:linear-gradient(90deg,var(--loss),#FF8A96)}

/* === 链接按钮 === */
.links{display:flex;flex-wrap:wrap;gap:10px;margin-top:17px}
.lk{font-family:var(--mono);font-size:12px;letter-spacing:.08em;color:var(--amber);font-weight:600;
  background:var(--panel);border:1px solid var(--line);padding:9px 15px;
  border-radius:999px;box-shadow:var(--shadow-sm)}
.lk:active{transform:scale(.97)}

/* === 队伍格 === */
.team-grid{display:grid;gap:13px;grid-template-columns:repeat(auto-fit,minmax(150px,1fr))}
.tc{background:var(--panel);border:1px solid var(--line);border-radius:22px;padding:17px 14px;text-align:center;
  box-shadow:var(--shadow-sm);position:relative;overflow:hidden}
.tc::before{content:"";position:absolute;top:0;left:0;right:0;height:4px;background:var(--grad);opacity:.85}
.tc:active{transform:scale(.98)}
.tc .ph{width:80px;height:80px;margin:0 auto 11px}
.tc .ph .av,.tc .ph .av-ph{border-radius:20px}
.tc .pid{font-size:18px;font-weight:800;letter-spacing:.02em;color:var(--ink)}
.tc .pfull{font-family:var(--mono);font-size:11px;color:var(--ink2);margin-top:3px;letter-spacing:.04em}
.tc .prole{font-family:var(--mono);font-size:11px;color:var(--amber);background:var(--amber-bg);
  padding:4px 11px;display:inline-block;margin-top:8px;letter-spacing:.08em;font-weight:600;border-radius:999px}
.tc .pdesc{font-size:12px;color:var(--ink2);margin-top:7px;line-height:1.5}

/* === 准星（还原 NiKo 游戏内实际准星：深色画面 + 绿色细准星）=== */
.xh{display:grid;place-items:center;position:relative;overflow:hidden;
  height:152px;margin-top:11px;border-radius:20px;
  background:radial-gradient(120% 95% at 50% 0%, #242949 0%, #141830 55%, #0B0E1C 100%);
  border:1px solid rgba(255,255,255,.08);
  box-shadow:inset 0 0 70px rgba(0,0,0,.6)}
.xh::before{content:"";position:absolute;inset:0;pointer-events:none;
  background-image:linear-gradient(rgba(255,255,255,.045) 1px,transparent 1px),
                   linear-gradient(90deg,rgba(255,255,255,.045) 1px,transparent 1px);
  background-size:38px 38px;
  mask-image:radial-gradient(closest-side,#000 60%,transparent)}
.xh i{position:absolute;background:var(--xh);border-radius:1px;
  box-shadow:0 0 6px rgba(0,255,145,.55)}

/* === 页脚 === */
.foot{margin-top:36px;padding-top:20px;border-top:1px solid var(--line-soft);
  font-family:var(--mono);font-size:12px;color:var(--ink2);line-height:1.9;letter-spacing:.04em}
.foot a{color:var(--amber);font-weight:600}
.syncbar{display:flex;align-items:center;gap:9px;margin-top:17px;font-family:var(--mono);font-size:12px;color:var(--ink2);
  background:var(--panel);padding:10px 15px;border:1px solid var(--line);border-radius:999px;
  box-shadow:var(--shadow-sm)}
.syncbar .lk{background:var(--amber-bg);border-color:transparent}
.empty{padding:30px 14px;text-align:center;color:var(--ink2);font-family:var(--mono);font-size:13px;
  background:var(--panel2);border:1px dashed var(--line-soft);border-radius:20px;margin-top:9px}
.back{margin-top:17px}

/* ==== CS 武器背景 ==== */
.arms{position:fixed;inset:0;z-index:0;pointer-events:none;overflow:hidden;
  transform:translate3d(0,var(--sy,0px),0);transition:transform .6s cubic-bezier(.22,.9,.3,1)}
.arm{position:absolute;height:auto;color:var(--ink);fill:currentColor;opacity:.09;
  transform:rotate(var(--r,0deg));animation:armDrift var(--d,26s) ease-in-out infinite;animation-delay:var(--dl,0s)}
@keyframes armDrift{0%,100%{transform:rotate(var(--r,0deg)) translate3d(0,0,0)}50%{transform:rotate(var(--r,0deg)) translate3d(0,-18px,0)}}
.arm-1{--r:-9deg;--d:30s;width:60vw;max-width:660px;right:-9vw;top:8vh;opacity:.1;color:var(--amber2)}
.arm-2{--r:8deg;--d:26s;--dl:-6s;width:46vw;max-width:500px;left:-12vw;top:32vh}
.arm-3{--r:-6deg;--d:34s;--dl:-14s;width:42vw;max-width:460px;right:-7vw;top:56vh;opacity:.075}
.arm-4{--r:-16deg;--d:22s;--dl:-3s;width:19vw;max-width:200px;left:5vw;top:16vh;opacity:.07}
.arm-5{--r:14deg;--d:24s;--dl:-9s;width:22vw;max-width:230px;right:8vw;bottom:7vh;opacity:.08;color:var(--cyan)}
.arm-6{--r:-10deg;--d:20s;--dl:-5s;width:12vw;max-width:128px;left:24vw;bottom:14vh;opacity:.07}
.arm-7{--r:18deg;--d:28s;--dl:-11s;width:11vw;max-width:118px;left:6vw;bottom:3vh;opacity:.065}
.hero-arms{position:absolute;right:-8%;bottom:-8%;width:64%;z-index:0;pointer-events:none;
  color:rgba(255,255,255,.92);fill:currentColor;opacity:.14;animation:heroArm 18s ease-in-out infinite}
@keyframes heroArm{0%,100%{transform:translate3d(0,0,0) rotate(0deg)}50%{transform:translate3d(-12px,-9px,0) rotate(-1.6deg)}}

/* ==== 点击反馈 ==== */
.wrap{position:relative;z-index:1}
a,button,.row,.pc,.tc,.lk,.more,.up-c,.st,.map,.prof,.syncbar{
  position:relative;overflow:hidden;
  transition:transform .18s cubic-bezier(.2,.9,.3,1.35),box-shadow .3s ease,background-color .3s ease,border-color .3s ease,color .3s ease}
a:active,button:active,.row:active,.pc:active,.tc:active,.lk:active,.more:active,
.up-c:active,.st:active,.map:active,.prof:active,.pressed{transform:scale(.972)}
.ripple{position:absolute;border-radius:50%;pointer-events:none;z-index:3;
  background:radial-gradient(circle,rgba(91,92,230,.5) 0%,rgba(139,92,246,.25) 42%,rgba(139,92,246,0) 72%);
  animation:ripple .62s cubic-bezier(.2,.7,.3,1) forwards}
@keyframes ripple{from{transform:scale(0);opacity:.95}to{transform:scale(2.4);opacity:0}}
.hitmark{position:absolute;width:24px;height:24px;margin:-12px 0 0 -12px;pointer-events:none;z-index:4;animation:hit .5s cubic-bezier(.2,.8,.3,1) forwards}
.hitmark::before,.hitmark::after{content:"";position:absolute;left:50%;top:50%;width:2px;height:19px;margin:-9.5px 0 0 -1px;background:var(--amber);border-radius:2px}
.hitmark::before{transform:rotate(45deg)}
.hitmark::after{transform:rotate(-45deg)}
@keyframes hit{0%{transform:scale(.35) rotate(-25deg);opacity:0}25%{transform:scale(1) rotate(0deg);opacity:.95}100%{transform:scale(1.35) rotate(8deg);opacity:0}}
@media(hover:hover){
  .row:hover,.pc:hover,.tc:hover,.up-c:hover,.st:hover,.map:hover,.prof:hover{
    transform:translateY(-4px);box-shadow:var(--shadow-lg);border-color:var(--line-soft)}
  .lk:hover{background:var(--amber);color:#fff;border-color:transparent;transform:translateY(-2px);
    box-shadow:0 14px 26px -14px rgba(91,92,230,.75)}
  .more:hover{background:var(--amber-bg);border-color:var(--amber2)}
  .crosshair:hover{transform:rotate(90deg) scale(1.08)}
}
.crosshair{transition:transform .45s cubic-bezier(.2,.9,.3,1.5),box-shadow .3s ease}

/* ==== 过渡动画 ==== */
@keyframes pageIn{from{opacity:0;transform:translateY(14px)}}
@keyframes hudIn{from{opacity:0;transform:translateY(-100%)}}
.wrap{animation:pageIn .55s cubic-bezier(.22,.9,.3,1) backwards}
.hud{animation:hudIn .5s cubic-bezier(.22,.9,.3,1) backwards}
@keyframes riseIn{from{opacity:0;transform:translateY(18px) scale(.99)}to{opacity:1;transform:none}}
.rv{opacity:0}
.rv.in{animation:riseIn .6s cubic-bezier(.22,.9,.3,1) forwards;animation-delay:var(--rd,0s)}
body.leaving .wrap{opacity:0;transform:translateY(-10px);transition:opacity .2s ease,transform .2s ease}
body.leaving .hud,body.leaving .arms{opacity:0;transition:opacity .2s ease}

@media(prefers-reduced-motion:reduce){
  .arm,.hero-arms,.wrap,.hud{animation:none!important}
  .rv{opacity:1!important}
  .ripple,.hitmark{display:none!important}
  *{transition-duration:.01ms!important}
}

/* ========== 真实地图背景（历史战绩里每张地图用该地图实景图） ========== */
.map.has-bg{--mimg:none;--mlqip:none;background:#0E1024;border-color:rgba(255,255,255,.14);isolation:isolate}
/* 四层背景（从上到下）：竖向压暗 → 横向压暗(左重右轻，文字在左) → 地图实景 → 模糊占位 */
.map.has-bg::before{content:'';position:absolute;inset:0;z-index:0;
  background-image:
    linear-gradient(180deg,rgba(5,7,18,.34) 0%,rgba(5,7,18,.26) 45%,rgba(5,7,18,.52) 100%),
    linear-gradient(96deg,rgba(5,7,18,.52) 0%,rgba(5,7,18,.16) 58%,rgba(5,7,18,.04) 100%),
    var(--mimg),
    var(--mlqip);
  background-size:cover,cover,cover,cover;
  background-position:center,center,center,center;
  background-repeat:no-repeat;
  filter:saturate(1.08) contrast(1.04);
  transform:scale(1.03);transition:transform .85s cubic-bezier(.2,.7,.3,1)}
.map.has-bg:hover::before{transform:scale(1.11)}
.map.has-bg>*{position:relative;z-index:1}
.map.has-bg .map-h b{color:#fff;text-shadow:0 1px 3px rgba(0,0,0,.9),0 2px 18px rgba(0,0,0,.7)}
.map.has-bg .map-h em{background:rgba(8,10,22,.55);color:rgba(255,255,255,.95);
  backdrop-filter:blur(3px);-webkit-backdrop-filter:blur(3px);text-shadow:0 1px 2px rgba(0,0,0,.6)}
.map.has-bg .map-en{color:rgba(255,255,255,.72);text-shadow:0 1px 3px rgba(0,0,0,.8)}
.map.has-bg .mline .who{color:rgba(255,255,255,.9);text-shadow:0 1px 3px rgba(0,0,0,.85)}
.map.has-bg .mline .rounds{color:#fff;text-shadow:0 1px 4px rgba(0,0,0,.9)}
.map.has-bg .mline .halves{color:rgba(255,255,255,.8);text-shadow:0 1px 3px rgba(0,0,0,.85)}
.map.has-bg .mline .tbar{background:rgba(255,255,255,.22);box-shadow:0 0 0 1px rgba(0,0,0,.25)}
.map.has-bg .map-res{box-shadow:0 1px 10px rgba(0,0,0,.5)}
.map.has-bg.veto{opacity:.72}
.map.has-bg.veto::before{filter:grayscale(.92) brightness(.72)}
.map.has-bg .mbg-en{position:absolute;right:12px;bottom:-8px;z-index:0;font-family:var(--tech);
  font-weight:700;font-size:52px;letter-spacing:.08em;line-height:1;color:rgba(255,255,255,.13);
  text-shadow:0 2px 10px rgba(0,0,0,.5);
  text-transform:uppercase;pointer-events:none;user-select:none;white-space:nowrap}
@media(max-width:440px){.map.has-bg .mbg-en{font-size:36px;right:10px}}

/* ========== 赛事中心（当前赛事 / 分组 / 分支图 / 实时比分） ========== */
.ev-tabs{display:flex;gap:8px;overflow-x:auto;padding:2px 0 10px;scrollbar-width:none;-webkit-overflow-scrolling:touch}
.ev-tabs::-webkit-scrollbar{display:none}
.ev-tab{flex:none;padding:9px 15px;border-radius:14px;border:1px solid var(--line);background:var(--panel);
  cursor:pointer;transition:transform .2s,box-shadow .26s,background .26s;text-align:left}
.ev-tab b{display:block;font-size:13.5px;font-weight:700;color:var(--ink);white-space:nowrap}
.ev-tab small{display:block;font-family:var(--mono);font-size:10px;color:var(--ink2);letter-spacing:.05em;margin-top:1px}
.ev-tab.on{background:var(--grad);border-color:transparent;box-shadow:var(--glow)}
.ev-tab.on b{color:#fff}
.ev-tab.on small{color:rgba(255,255,255,.82)}

.ev-card{background:var(--panel);border:1px solid var(--line);border-radius:22px;padding:18px;
  box-shadow:var(--shadow-sm);position:relative;overflow:hidden}
.ev-card::after{content:'';position:absolute;inset:0 0 auto 0;height:4px;background:var(--grad)}
.ev-top{display:flex;align-items:flex-start;gap:12px;flex-wrap:wrap}
.ev-name{font-family:var(--display);font-weight:700;font-size:23px;line-height:1.3}
.ev-badge{margin-left:auto;display:flex;gap:6px;flex:none;flex-wrap:wrap}
.ev-b{font-family:var(--mono);font-size:11px;letter-spacing:.08em;padding:4px 10px;border-radius:999px;font-weight:600}
/* 注意：状态类必须带前缀（s-），否则会和已有的 .up{display:grid}（未来赛程网格）撞车 */
.ev-b.s-live{background:var(--loss);color:#fff;animation:evpulse 1.7s infinite}
.ev-b.s-up{background:var(--amber-bg);color:var(--amber)}
.ev-b.s-done{background:var(--panel3);color:var(--ink2)}
.ev-b.gold{background:linear-gradient(120deg,#F6C86E,#E39A2E);color:#3A2A05}
@keyframes evpulse{0%,100%{box-shadow:0 0 0 0 rgba(240,86,110,.5)}50%{box-shadow:0 0 0 8px rgba(240,86,110,0)}}
.ev-meta{display:grid;grid-template-columns:repeat(2,1fr);gap:9px;margin-top:14px}
.ev-mi{background:var(--panel2);border-radius:13px;padding:9px 12px}
.ev-mi span{display:block;font-size:10.5px;color:var(--ink2);letter-spacing:.06em}
.ev-mi b{display:block;font-family:var(--tech);font-size:16px;font-weight:700;color:var(--ink);margin-top:1px}
.ev-fmt{margin-top:12px;font-size:13.5px;color:var(--ink2);line-height:1.7;
  border-left:3px solid var(--line-soft);padding-left:11px}
.ev-cta{display:inline-flex;align-items:center;gap:7px;margin-top:14px;padding:10px 16px;border-radius:14px;
  background:var(--grad);color:#fff;font-size:14px;font-weight:700;box-shadow:var(--shadow-md);transition:transform .2s}
.ev-cta:active{transform:scale(.97)}
.ev-count{display:flex;gap:8px;margin-top:14px}
.ev-cd{flex:1;text-align:center;background:var(--grad-soft);border-radius:14px;padding:9px 4px;border:1px solid var(--line)}
.ev-cd b{display:block;font-family:var(--tech);font-weight:700;font-size:26px;line-height:1.15;color:var(--ink)}
.ev-cd span{font-size:10px;color:var(--ink2);letter-spacing:.08em}

.teams{display:grid;grid-template-columns:repeat(auto-fill,minmax(102px,1fr));gap:9px}
.tm{display:flex;align-items:center;gap:7px;background:var(--panel);border:1px solid var(--line);
  border-radius:13px;padding:8px 9px;box-shadow:var(--shadow-sm);overflow:hidden}
.tm.hl{border-color:rgba(91,92,230,.5);background:var(--grad-soft);box-shadow:var(--glow)}
.tm img{width:22px;height:24px;object-fit:contain;flex:none}
.tm em{font-style:normal;font-size:12.5px;font-weight:600;color:var(--ink);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tm .mono{font-family:var(--tech);font-size:15px;font-weight:700;color:var(--ink2)}

/* 分支图：严格自适应窗口缩放，固定不滑动（2026-10-08 二次改造）
   2026-10-05：列宽 104px 固定 + JS 按比例 scale，但保留了 overflow-x:auto
   和 0.4 缩放下限 → 列多时仍会溢出、能拖动滑来滑去。
   现在：彻底去掉 overflow（任何窗口宽度都不产生滚动条），
   列宽改为「均分容器」，match 卡内容用 clamp() 随宽度平滑缩放，
   JS 只在极端情况（列数极多）做兜底缩放，且不再有下限。 */
.brk-wrap{padding:2px 0 6px;position:relative}
.brk{display:flex;gap:clamp(3px,1.4vw,10px);width:100%;align-items:stretch;transform-origin:top left}
.brk-r{display:flex;flex-direction:column;flex:1 1 0;min-width:0}
.brk-rb{display:flex;flex-direction:column;justify-content:space-around;gap:6px;flex:1}
.brk-rt{font-family:var(--display);font-size:clamp(9px,calc(var(--cw,.22)*.105),15px);
  font-weight:700;color:var(--ink2);
  letter-spacing:.02em;padding-left:1px;margin-bottom:5px;flex:none;text-align:center;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.brk-m{background:var(--panel);border:1px solid var(--line);border-radius:9px;overflow:hidden;
  box-shadow:var(--shadow-sm);transition:transform .22s,box-shadow .26s}
.brk-m:hover{transform:translateY(-2px);box-shadow:var(--shadow-md)}
.brk-m.live{border-color:var(--loss);box-shadow:0 0 0 2px rgba(240,86,110,.22)}
/* 紧凑条：一行 = 队标 + 缩写 + 比分。所有尺寸基于 --cw（列宽，由 JS 按容器实测写入）
   做 calc 派生，并用 clamp() 双向封顶：窄屏随列宽同比缩小（不溢出、不出滚动条），
   宽屏封顶在正常字号（否则列一宽字就变得巨大）。 */
.brk-o{display:flex;align-items:center;gap:clamp(2px,calc(var(--cw,.22)*.035),7px);
  padding:clamp(2px,calc(var(--cw,.22)*.028),8px) clamp(3px,calc(var(--cw,.22)*.045),14px);
  font-size:clamp(8.5px,calc(var(--cw,.22)*.1),14px);min-width:0}
.brk-o+.brk-o{border-top:1px solid var(--line)}
.brk-o img{width:clamp(9px,calc(var(--cw,.22)*.13),19px);
  height:clamp(10px,calc(var(--cw,.22)*.14),21px);object-fit:contain;flex:none}
.brk-o em{font-style:normal;flex:1;min-width:0;white-space:nowrap;overflow:hidden;
  text-overflow:ellipsis;color:var(--ink2);font-weight:600;letter-spacing:.01em}
.brk-o s{text-decoration:none;font-family:var(--tech);font-weight:700;
  font-size:clamp(10px,calc(var(--cw,.22)*.115),16px);color:var(--ink2);flex:none;
  margin-left:auto;padding-left:clamp(2px,calc(var(--cw,.22)*.028),7px)}
.brk-o.w{background:linear-gradient(90deg,rgba(0,255,145,.10),transparent)}
.brk-o.w em{color:var(--ink);font-weight:700}
.brk-o.w s{color:var(--win)}
.brk-o.l{opacity:.55}
.brk-o.l s{color:var(--dim)}
.brk-mt{font-family:var(--mono);font-size:clamp(7.5px,calc(var(--cw,.22)*.082),11px);
  color:var(--dim);
  padding:clamp(1.5px,calc(var(--cw,.22)*.02),5px) clamp(3px,calc(var(--cw,.22)*.045),14px);
  background:var(--panel2);letter-spacing:.02em;display:flex;
  gap:clamp(2px,calc(var(--cw,.22)*.045),8px);align-items:center;
  white-space:nowrap;overflow:hidden}
.brk-mt i{font-style:normal;color:var(--loss);font-weight:700;margin-left:auto;flex:none}

.sch-d{font-family:var(--display);font-size:13px;font-weight:700;color:var(--ink2);margin:14px 0 7px}
.sch{display:flex;align-items:center;gap:10px;background:var(--panel);border:1px solid var(--line);
  border-radius:14px;padding:9px 12px;margin-bottom:7px;box-shadow:var(--shadow-sm)}
.sch.live{border-color:var(--loss)}
.sch .t{font-family:var(--tech);font-size:14px;font-weight:700;color:var(--ink2);flex:none;width:44px}
.sch .n{flex:1;font-size:13.5px;color:var(--ink);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.sch .n b{font-weight:700}
.sch .s{font-family:var(--tech);font-weight:700;font-size:15px;flex:none}
.sch .q{font-family:var(--mono);font-size:10px;color:var(--dim);flex:none}
.tag-live{font-family:var(--mono);font-size:10px;font-weight:700;color:#fff;
  background:var(--loss);padding:2px 7px;border-radius:999px}

/* === 分组积分：排行榜（队标 + 队名 + 战绩 + 各轮结果） ===
   ⚠️ 分区类必须带 z- 前缀：项目里已有 `.up{display:grid}`（未来赛程网格），
   直接叫 .up 会把排行榜行变成 grid、把两行挤成一行。 */
.lb{display:flex;flex-direction:column;gap:8px}
.lb-r{position:relative;background:var(--panel);border:1px solid var(--line);border-radius:16px;
  padding:9px 12px 9px 15px;box-shadow:var(--shadow-sm);overflow:hidden;
  transition:transform .2s,box-shadow .24s}
.lb-r::before{content:'';position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--line-soft)}
.lb-r.z-up::before{background:var(--win)}
.lb-r.z-down::before{background:var(--loss)}
.lb-r.hl{background:var(--grad-soft);border-color:var(--line-soft)}
.lb-r.hl::before{background:var(--grad)}
@media(hover:hover){.lb-r:hover{transform:translateY(-2px);box-shadow:var(--shadow-md)}}
.lb-main{display:flex;align-items:center;gap:10px;min-width:0}
.lb-rk{flex:none;width:27px;height:27px;border-radius:9px;display:grid;place-items:center;
  font-family:var(--tech);font-size:14px;font-weight:700;line-height:1;color:var(--ink2);
  background:var(--panel2);border:1px solid var(--line)}
.lb-rk.t1{background:linear-gradient(145deg,#F6C955,#DE9A13);color:#fff;border-color:transparent;
  box-shadow:0 7px 15px -8px rgba(222,154,19,.95)}
.lb-rk.t2{background:linear-gradient(145deg,#C2CDE2,#8E9DBC);color:#fff;border-color:transparent;
  box-shadow:0 7px 15px -8px rgba(142,157,188,.95)}
.lb-rk.t3{background:linear-gradient(145deg,#E5AB7E,#C1743C);color:#fff;border-color:transparent;
  box-shadow:0 7px 15px -8px rgba(193,116,60,.9)}
.lb-tm{display:flex;align-items:center;gap:9px;flex:1;min-width:0}
.lb-tm img{width:27px;height:27px;object-fit:contain;flex:none}
.lb-tm .ph{flex:none;width:27px;height:27px;border-radius:9px;display:grid;place-items:center;
  font-family:var(--tech);font-size:12px;font-weight:700;color:var(--amber);
  background:var(--grad-soft);border:1px solid var(--line)}
.lb-tm b{font-family:var(--tech);font-size:15.5px;font-weight:700;letter-spacing:.01em;color:var(--ink);
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.lb-tm b.hl{background:var(--grad-num);-webkit-background-clip:text;background-clip:text;
  -webkit-text-fill-color:transparent}
.lb-wl{flex:none;font-family:var(--tech);font-size:15px;font-weight:700;letter-spacing:.03em;
  padding:2px 10px;border-radius:10px;color:var(--ink2);background:var(--panel2);border:1px solid var(--line)}
.lb-wl.good{color:var(--win);background:var(--win-bg);border-color:rgba(21,185,129,.28)}
.lb-wl.bad{color:var(--loss);background:var(--loss-bg);border-color:rgba(240,86,110,.26)}
.lb-sub{display:flex;align-items:center;flex-wrap:wrap;gap:6px 8px;margin-top:6px;padding-left:37px}
.lb-m{font-family:var(--mono);font-size:11.5px;color:var(--dim);letter-spacing:.04em;white-space:nowrap}
.lb-m b{font-family:var(--tech);font-size:12.5px;font-weight:700;color:var(--ink2);letter-spacing:.02em}
.lb-m b.g{color:var(--win)}
.lb-m b.r{color:var(--loss)}
.lb-form{display:flex;gap:3px;margin-left:auto}
.lb-form i{min-width:24px;height:19px;padding:0 4px;border-radius:6px;display:grid;place-items:center;
  font-family:var(--tech);font-size:10.5px;font-weight:700;font-style:normal;letter-spacing:.01em}
.lb-form i.w{color:var(--win);background:var(--win-bg);border:1px solid rgba(21,185,129,.3)}
.lb-form i.l{color:var(--loss);background:var(--loss-bg);border:1px solid rgba(240,86,110,.3)}
.lb-form i.e{color:var(--dim);background:transparent;border:1px dashed var(--line-soft)}
.lb-foot{display:flex;align-items:center;flex-wrap:wrap;gap:5px;margin-top:10px;padding-left:2px;
  font-family:var(--mono);font-size:10.5px;color:var(--dim);letter-spacing:.05em}
.lb-foot b{display:inline-block;width:11px;height:11px;border-radius:3px;font-style:normal}
.lb-foot b.w{background:var(--win-bg);border:1px solid rgba(21,185,129,.55)}
.lb-foot b.l{background:var(--loss-bg);border:1px solid rgba(240,86,110,.55)}
/* 宽屏：整行收成一行 —— 队名弹性撑开，战绩/回合/各轮全部靠右对齐 */
@media(min-width:600px){
  .lb-r{display:flex;align-items:center;gap:14px}
  .lb-main{flex:1;min-width:0}
  .lb-sub{flex:0 0 auto;flex-wrap:nowrap;margin-top:0;padding-left:0;justify-content:flex-end}
  .lb-form{margin-left:0}
}

/* === 首页：当前赛事入口 === */
.hero-link{display:block;cursor:pointer}
.hero-cta{margin-top:14px;display:inline-flex;align-items:center;gap:8px;padding:9px 15px;border-radius:13px;
  background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.3);color:#fff;
  font-size:13.5px;font-weight:700;transition:background .24s,transform .2s}
.hero-cta span{font-family:var(--mono);opacity:.85}
.hero-link:hover .hero-cta{background:rgba(255,255,255,.28)}
.hero-link:active .hero-cta{transform:scale(.97)}
.ev-list{display:flex;flex-direction:column;gap:10px}
.ev-e{display:block;background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:14px 16px;
  box-shadow:var(--shadow-sm);position:relative;overflow:hidden;transition:transform .22s,box-shadow .26s}
.ev-e::before{content:'';position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--grad)}
.ev-e:hover{transform:translateY(-2px);box-shadow:var(--shadow-md)}
.ev-e-h{display:flex;align-items:center;gap:9px}
.ev-e-h b{font-family:var(--display);font-size:16px;font-weight:700;color:var(--ink)}
.ev-e-h .ev-b{margin-left:auto}
.ev-e-m{font-size:13px;color:var(--ink2);margin-top:2px}
.ev-e-d{font-family:var(--mono);font-size:11.5px;color:var(--dim);margin-top:5px;letter-spacing:.03em}
.ev-e-f{display:flex;gap:14px;margin-top:8px;font-family:var(--mono);font-size:11px;color:var(--ink2)}
.ev-e-go{margin-top:9px;font-size:12.5px;font-weight:700;color:var(--amber)}

/* ========== 选手页：顶部大图 + 官方照片墙 + 资料卡 ========== */
.phero{position:relative;border-radius:20px;overflow:hidden;margin-top:14px;
  background:#0E1024;box-shadow:var(--shadow-lg);isolation:isolate}
.phero-img{display:block;width:100%;height:clamp(252px,70vw,392px);object-fit:cover;
  object-position:center 20%;transform:scale(1.02);filter:brightness(1.08) saturate(1.06);
  transition:transform 1.1s cubic-bezier(.2,.7,.3,1)}
@media(hover:hover){.phero:hover .phero-img{transform:scale(1.06)}}
.phero-scrim{position:absolute;inset:0;z-index:1;pointer-events:none;
  background:
    linear-gradient(180deg,rgba(8,10,26,.02) 0%,rgba(8,10,26,.03) 34%,rgba(8,10,26,.36) 72%,rgba(8,10,26,.80) 100%),
    linear-gradient(100deg,rgba(8,10,26,.38) 0%,rgba(8,10,26,.08) 46%,rgba(8,10,26,0) 76%)}
.phero-id{position:absolute;left:18px;right:18px;bottom:16px;z-index:2}
.phero-name{font-family:var(--tech);font-size:clamp(38px,12vw,58px);font-weight:700;
  color:#fff;line-height:.96;letter-spacing:.01em;text-shadow:0 2px 24px rgba(0,0,0,.55)}
.phero-full{font-family:var(--mono);font-size:13px;color:rgba(255,255,255,.88);margin-top:7px;
  letter-spacing:.04em;text-shadow:0 1px 12px rgba(0,0,0,.6)}
.phero-meta{display:flex;flex-wrap:wrap;gap:7px;align-items:center;margin-top:10px;
  font-family:var(--mono);font-size:11.5px;color:rgba(255,255,255,.82);letter-spacing:.04em}
.phero-meta b{color:#fff;font-weight:700}
.phero-meta .sep{width:4px;height:4px;border-radius:50%;background:rgba(255,255,255,.55)}
.phero-badge{position:absolute;top:13px;left:13px;z-index:2;display:inline-flex;align-items:center;gap:6px;
  padding:5px 11px;border-radius:999px;background:rgba(10,12,30,.52);border:1px solid rgba(255,255,255,.24);
  -webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);
  font-family:var(--mono);font-size:10.5px;color:#fff;letter-spacing:.1em;text-transform:uppercase}
.phero-badge .dot{width:6px;height:6px;border-radius:50%;background:#3BE39B;box-shadow:0 0 8px #3BE39B}
.phero-gal{position:absolute;top:13px;right:13px;z-index:3;display:inline-flex;align-items:center;gap:5px;
  padding:6px 12px;border-radius:999px;border:1px solid rgba(255,255,255,.32);color:#fff;cursor:pointer;
  background:linear-gradient(120deg,rgba(91,92,230,.94),rgba(31,182,201,.9));
  -webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px);
  font-family:var(--mono);font-size:10.5px;font-weight:700;letter-spacing:.06em;
  box-shadow:0 8px 22px -10px rgba(0,0,0,.7)}
.phero-gal:active{transform:scale(.95)}

/* 关键数据 chips */
.pchips{display:flex;gap:9px;overflow-x:auto;padding:12px 2px 5px;scrollbar-width:none;margin:0 -2px}
.pchips::-webkit-scrollbar{display:none}
.chip{flex:0 0 auto;min-width:98px;background:var(--panel);border:1px solid var(--line);border-radius:14px;
  padding:10px 13px;box-shadow:var(--shadow-sm)}
.chip b{display:block;font-family:var(--tech);font-size:21px;font-weight:700;color:var(--ink);
  letter-spacing:.01em;line-height:1.1}
.chip.hl b{background:var(--grad-num);-webkit-background-clip:text;background-clip:text;
  -webkit-text-fill-color:transparent}
.chip span{display:block;font-family:var(--mono);font-size:10px;color:var(--ink2);letter-spacing:.1em;
  text-transform:uppercase;margin-top:4px}

/* 个人简介 */
.pbio{background:linear-gradient(180deg,var(--panel),var(--panel2));border:1px solid var(--line);
  border-radius:18px;padding:16px 17px;box-shadow:var(--shadow-sm);position:relative;overflow:hidden;
  margin-top:13px}
.pbio::before{content:"";position:absolute;left:0;top:0;bottom:0;width:5px;background:var(--grad)}
.pbio-h{font-family:var(--mono);font-size:11px;color:var(--amber);letter-spacing:.16em;
  text-transform:uppercase;font-weight:700;padding-left:8px}
.pbio p{margin-top:9px;padding-left:8px;font-size:14px;line-height:1.85;color:var(--ink2);letter-spacing:.01em}
.pbio p b{color:var(--ink);font-weight:700}

/* 官方照片墙（可横向滑动） */
.pwall{display:flex;gap:11px;overflow-x:auto;scroll-snap-type:x mandatory;
  padding:4px 14px 13px;margin:0 -14px;-webkit-overflow-scrolling:touch;scrollbar-width:thin;
  scrollbar-color:var(--line-soft) transparent}
.pwall::-webkit-scrollbar{height:5px}
.pwall::-webkit-scrollbar-thumb{background:var(--line-soft);border-radius:3px}
.pwall::-webkit-scrollbar-track{background:transparent}
.pw-item{flex:0 0 auto;width:172px;scroll-snap-align:start;position:relative;border-radius:15px;
  overflow:hidden;background:#0E1024;box-shadow:var(--shadow-md);cursor:zoom-in;
  transition:transform .35s cubic-bezier(.2,.7,.3,1),box-shadow .35s}
.pw-item:active{transform:scale(.973)}
@media(hover:hover){.pw-item:hover{transform:translateY(-4px);box-shadow:var(--shadow-lg)}}
.pw-item img{display:block;width:100%;height:228px;object-fit:cover;object-position:center 16%;
  filter:brightness(1.07) saturate(1.05);
  transition:transform .7s cubic-bezier(.2,.7,.3,1)}
@media(hover:hover){.pw-item:hover img{transform:scale(1.07)}}
.pw-cap{position:absolute;left:0;right:0;bottom:0;padding:24px 11px 9px;color:#fff;
  background:linear-gradient(180deg,rgba(6,8,20,0),rgba(6,8,20,.86) 60%,rgba(6,8,20,.96))}
.pw-cap b{display:block;font-size:12.5px;font-weight:700;letter-spacing:.01em;line-height:1.28;
  text-shadow:0 1px 8px rgba(0,0,0,.5)}
.pw-cap span{display:block;font-family:var(--mono);font-size:10.5px;color:rgba(255,255,255,.72);margin-top:3px}
.pw-new{position:absolute;top:9px;left:9px;z-index:2;padding:3px 9px;border-radius:999px;
  background:linear-gradient(120deg,#5B5CE6,#1FB6C9);font-family:var(--mono);font-size:9.5px;
  color:#fff;letter-spacing:.14em;font-weight:700;box-shadow:0 4px 12px -4px rgba(0,0,0,.6)}
.pw-hint{font-family:var(--mono);font-size:11px;color:var(--dim);text-align:center;letter-spacing:.1em;
  margin-top:1px}
.pw-all{display:block;margin:12px auto 0;padding:9px 20px;border-radius:999px;border:1px solid var(--line-soft);
  background:var(--panel);color:var(--amber);font-family:var(--mono);font-size:12px;font-weight:700;
  letter-spacing:.08em;cursor:pointer}
.pw-all:active{transform:scale(.97)}

/* 个人资料（分组卡片） */
.pinfo{display:grid;gap:12px}
.pcard{background:linear-gradient(180deg,var(--panel),var(--panel2));border:1px solid var(--line);
  border-radius:18px;padding:15px 16px;box-shadow:var(--shadow-sm);position:relative}
.pcard-h{display:flex;align-items:center;gap:9px;margin-bottom:13px}
.pcard-h b{font-family:var(--display);font-size:15px;font-weight:700;color:var(--ink);letter-spacing:.03em;
  position:relative;padding-left:13px}
.pcard-h b::before{content:"";position:absolute;left:0;top:.12em;bottom:.12em;width:4px;border-radius:2px;
  background:var(--grad)}
.pcard-h em{font-family:var(--mono);font-size:10.5px;color:var(--dim);font-style:normal;letter-spacing:.1em;
  margin-left:auto}
.pgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(116px,1fr));gap:12px 14px}
.pgrid.one{grid-template-columns:1fr}
.pi{min-width:0}
.pi-k{font-family:var(--mono);font-size:10px;color:var(--dim);letter-spacing:.12em;text-transform:uppercase}
.pi-v{margin-top:4px;font-size:14px;color:var(--ink);font-weight:600;letter-spacing:.01em;
  word-break:break-word;line-height:1.5}
.pi-v.mono{font-family:var(--mono);font-size:12.5px;font-weight:500}
.pi-v.grad{background:var(--grad-num);-webkit-background-clip:text;background-clip:text;
  -webkit-text-fill-color:transparent;font-family:var(--tech);font-size:17px;font-weight:700}
.pcard .kw{display:inline-flex;align-items:center;padding:3px 9px;border-radius:999px;
  background:var(--amber-bg);color:var(--amber);font-family:var(--mono);font-size:11px;font-weight:600;
  margin:3px 5px 0 0}

/* 照片墙灯箱 */
.plb{position:fixed;inset:0;z-index:9999;display:none;align-items:center;justify-content:center;
  flex-direction:column;padding:22px;background:rgba(5,7,18,.94);
  -webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px)}
.plb.on{display:flex;animation:plbIn .22s ease}
@keyframes plbIn{from{opacity:0}to{opacity:1}}
.plb-img{max-width:94vw;max-height:78vh;border-radius:14px;object-fit:contain;
  box-shadow:0 30px 80px -20px rgba(0,0,0,.8);animation:plbZoom .28s cubic-bezier(.2,.8,.3,1)}
@keyframes plbZoom{from{transform:scale(.94);opacity:0}to{transform:scale(1);opacity:1}}
.plb-cap{margin-top:15px;font-family:var(--mono);font-size:12.5px;color:rgba(255,255,255,.9);
  letter-spacing:.06em;text-align:center}
.plb-x{position:absolute;top:16px;right:18px;width:38px;height:38px;border-radius:50%;
  background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.28);color:#fff;font-size:17px;
  display:flex;align-items:center;justify-content:center;cursor:pointer}
.plb-nav{position:absolute;top:50%;transform:translateY(-50%);width:44px;height:64px;border-radius:12px;
  background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.2);color:#fff;font-size:24px;
  display:flex;align-items:center;justify-content:center;cursor:pointer;user-select:none}
.plb-nav.l{left:14px}.plb-nav.r{right:14px}

/* ========== 首页 NiKo 资料卡（大图 + 官方照片墙） ========== */
.ncard{margin-top:18px;background:var(--panel);border:1px solid var(--line);border-radius:26px;
  overflow:hidden;box-shadow:var(--shadow-lg);position:relative}
.nhero{position:relative;height:clamp(304px,88vw,432px);overflow:hidden;background:#0E1024;isolation:isolate}
.nhero-img{display:block;width:100%;height:100%;object-fit:cover;object-position:center 18%;
  transform:scale(1.02);filter:brightness(1.08) saturate(1.06);
  transition:transform 1.2s cubic-bezier(.2,.7,.3,1)}
@media(hover:hover){.ncard:hover .nhero-img{transform:scale(1.07)}}
/* 遮罩刻意做透：只在最下沿压暗保证文字可读，中间几乎不遮 */
.nhero-scrim{position:absolute;inset:0;z-index:1;pointer-events:none;
  background:
    linear-gradient(180deg,rgba(8,10,26,.06) 0%,rgba(8,10,26,0) 32%,rgba(8,10,26,.26) 68%,rgba(8,10,26,.80) 100%),
    linear-gradient(96deg,rgba(8,10,26,.34) 0%,rgba(8,10,26,.06) 42%,rgba(8,10,26,0) 72%)}
.nhero-id{position:absolute;left:0;right:0;bottom:0;z-index:2;padding:0 18px 17px}
.nhero-name{font-family:var(--tech);font-size:clamp(40px,13.5vw,60px);font-weight:700;color:#fff;
  line-height:.96;letter-spacing:.01em;text-shadow:0 2px 26px rgba(0,0,0,.55)}
.nhero-full{font-family:var(--mono);font-size:12.5px;color:rgba(255,255,255,.9);margin-top:7px;
  letter-spacing:.04em;text-shadow:0 1px 12px rgba(0,0,0,.65)}
.nhero-meta{display:flex;flex-wrap:wrap;gap:7px;align-items:center;margin-top:9px;
  font-family:var(--mono);font-size:11.5px;color:rgba(255,255,255,.86);letter-spacing:.04em;
  text-shadow:0 1px 10px rgba(0,0,0,.7)}
.nhero-meta b{color:#fff;font-weight:700}
.nhero-meta .sep{width:3px;height:3px;border-radius:50%;background:rgba(255,255,255,.5)}
.ncard-body{padding:0 15px 15px}
.ncard-body .pchips{padding-top:13px}
.nwall-h{display:flex;align-items:baseline;gap:9px;margin:16px 0 10px}
.nwall-h b{font-family:var(--display);font-size:16px;font-weight:700;color:var(--ink)}
.nwall-h em{font-family:var(--mono);font-size:11px;color:var(--dim);font-style:normal;letter-spacing:.1em}
.ncard-go{display:flex;align-items:center;justify-content:space-between;margin-top:14px;
  padding:13px 16px;border-radius:15px;background:linear-gradient(120deg,#4738C8,#6B49D6 55%,#1F9FB4);
  color:#fff;font-size:13.5px;font-weight:700;letter-spacing:.02em;
  box-shadow:0 14px 30px -14px rgba(71,56,200,.7)}
.ncard-go span{font-size:18px;opacity:.9}
.ncard-go:active{transform:scale(.985)}

/* 赛事卡里的参赛队伍 logo 墙 */
.ev-e-lg{display:flex;align-items:center;gap:5px;flex-wrap:wrap;margin-top:10px}
.ev-e-lg img{width:22px;height:22px;object-fit:contain;background:#fff;border-radius:6px;padding:2px;
  border:1px solid var(--line);box-shadow:var(--shadow-sm)}
.ev-e-more{font-family:var(--mono);font-size:10.5px;color:var(--dim);padding:0 2px}

/* 队友卡：改成照片卡（照片 + 名字压角） */
.pc{flex:0 0 152px;padding:0;text-align:left}
.pc::before{height:3px}
.pc-ph{position:relative;height:112px;overflow:hidden;background:#0E1024}
.pc-ph img{display:block;width:100%;height:100%;object-fit:cover;object-position:center 20%;
  filter:brightness(1.07) saturate(1.05);
  transition:transform .8s cubic-bezier(.2,.7,.3,1)}
@media(hover:hover){.pc:hover .pc-ph img{transform:scale(1.08)}}
.pc-ph::after{content:'';position:absolute;inset:0;
  background:linear-gradient(180deg,rgba(8,10,26,0) 42%,rgba(8,10,26,.74) 100%)}
.pc-ph-txt{display:flex;align-items:center;justify-content:center;height:100%;
  font-family:var(--tech);font-size:34px;font-weight:700;color:rgba(255,255,255,.55);
  background:linear-gradient(135deg,rgba(71,56,200,.55),rgba(31,159,180,.48))}
.pc-id{position:absolute;left:11px;right:11px;bottom:9px;z-index:2;color:#fff;
  font-size:15px;font-weight:700;letter-spacing:.02em;text-shadow:0 1px 12px rgba(0,0,0,.6);
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.pc-meta{padding:11px 12px 13px}
.pc .prole{margin-top:0}
.pc .pnat{margin-top:6px}

/* 移动端微调 */
@media(max-width:380px){
  .hud-in{padding:10px 12px;gap:9px}
  .brand b{font-size:21px}
  .prof .nick{font-size:23px}
  .team{font-size:26px}
  .hero-team{width:88px;gap:7px}
  .hero-team img,.hero-logo-ph{width:56px;height:56px}
  .hero-team b{font-size:15px}
  .cd b{font-size:34px}
  .row{padding:12px 12px;gap:10px}
  .res{width:28px;height:28px;font-size:12px}
  .sc{width:52px;font-size:16px}
  .pw-item{width:150px}
  .pw-item img{height:200px}
  .pgrid{grid-template-columns:repeat(auto-fit,minmax(104px,1fr))}
}
/* ===== 赛事中心对阵卡：可点进比赛详情页 ===== */
.brk-lk,.sch-lk{display:block;color:inherit;text-decoration:none;position:relative;
  transition:transform .15s ease}
.brk-lk:hover .brk-m,.sch-lk:hover .sch{box-shadow:0 0 0 2px var(--amber-bg),
  0 10px 24px rgba(91,92,230,.20)}
.brk-go,.sch-go{position:absolute;right:10px;top:50%;transform:translateY(-50%);
  color:var(--dim);font-size:22px;font-weight:700;opacity:0;transition:opacity .15s;
  pointer-events:none}
/* 分支图卡片只有 104px 宽，箭头会压住比分——整卡仍可点进详情，就不显示箭头了 */
.brk-go{display:none}
.brk-lk:hover .brk-m,.sch-lk:hover .sch{box-shadow:0 0 0 2px var(--amber-bg),
  0 10px 24px rgba(91,92,230,.20)}
.sch-lk:hover .sch-go{opacity:1}
@media(hover:none){.sch-go{opacity:.5}}
"""

# ===== CS 经典武器剪影（内联 SVG sprite，纯几何图形绘制）=====
# 右滑返回：在「除首页外的」所有二级页面，从屏幕左侧向右横滑即返回上一级页面。
# 目标优先取页面内的「‹ 返回」链接（保证回到逻辑上级，而非随意的历史栈），无链接/无历史时回首页。
# 横向滑动容器（照片墙/灯箱/标签条/横滑卡片/选手 chips）内不抢手势，避免与容器自身横滑冲突。
SWIPE_BACK_JS = """<script>
(function(){
  var pid = (document.body && document.body.getAttribute('data-page')) || '';
  if(pid === 'index') return;                 // 首页不启用右滑返回
  var sx = 0, sy = 0, fired = false, locked = false;
  var SKIP = '.pwall,.plb,.ev-tabs,.eboard,.scroller,.pchips';
  function goBack(){
    if(locked) return; locked = true;
    var a = document.querySelector('.back a.lk');
    var href = a && a.getAttribute('href');
    if(href && /^\\w[\\w.-]*\\.html/.test(href)){ location.href = href; }   // 回到逻辑上级
    else if(history.length > 1){ history.back(); }
    else { location.href = 'index.html'; }
  }
  document.addEventListener('touchstart', function(e){
    var t = e.touches[0]; sx = t.clientX; sy = t.clientY; fired = false; locked = false;
    if(e.target && e.target.closest && e.target.closest(SKIP)) fired = true;
  }, {passive:true});
  document.addEventListener('touchmove', function(e){
    if(fired || locked) return;
    var t = e.touches[0];
    var dx = t.clientX - sx, dy = t.clientY - sy;
    /* 左缘起手 + 明确的向右横滑（幅度够大、且明显比纵向滑动更水平） */
    if(sx < 70 && dx > 100 && dx > Math.abs(dy) * 2.2){ fired = true; goBack(); }
  }, {passive:true});
})();
</script>"""
ARMS_SPRITE = """<svg id="armsSprite" aria-hidden="true"
  style="position:absolute;width:0;height:0;overflow:hidden">
  <symbol id="w-awp" viewBox="0 0 240 90"><g fill="currentColor">
    <path d="M2 30 L2 58 L34 54 L62 50 L96 48 L96 29 Z"/>
    <path d="M46 29 L80 21 L96 21 L96 29 Z"/>
    <rect x="96" y="26" width="62" height="22" rx="3"/>
    <rect x="106" y="12" width="52" height="13" rx="4"/>
    <rect x="98" y="13" width="11" height="12" rx="3"/>
    <rect x="152" y="10" width="17" height="18" rx="5"/>
    <rect x="112" y="24" width="6" height="5"/><rect x="146" y="24" width="6" height="5"/>
    <rect x="156" y="34" width="74" height="8"/><rect x="224" y="31" width="14" height="14" rx="2"/>
    <path d="M112 48 L134 48 L138 70 L116 70 Z"/><path d="M98 48 L114 48 L110 70 L96 68 Z"/>
    <path d="M120 52 L127 52 L125 60 L118 60 Z"/>
    <path d="M186 42 L193 42 L205 68 L199 68 Z"/><path d="M176 42 L182 42 L172 68 L166 68 Z"/>
    <rect x="140" y="49" width="15" height="7" rx="3"/>
  </g></symbol>
  <symbol id="w-ak" viewBox="0 0 240 90"><g fill="currentColor">
    <path d="M2 34 L92 28 L92 48 L46 50 L2 50 Z"/>
    <rect x="88" y="25" width="36" height="24" rx="2"/>
    <rect x="112" y="19" width="13" height="8" rx="1"/>
    <rect x="122" y="30" width="48" height="14" rx="3"/>
    <rect x="122" y="22" width="42" height="7" rx="2"/>
    <rect x="166" y="32" width="58" height="7"/><rect x="216" y="30" width="11" height="11" rx="2"/>
    <rect x="200" y="20" width="7" height="13"/>
    <path d="M100 49 L124 49 C136 60 142 72 142 84 L120 82 C118 70 110 58 100 49 Z"/>
    <path d="M86 49 L102 49 L98 72 L84 70 Z"/>
    <path d="M104 53 L111 53 L109 61 L103 61 Z"/>
    <rect x="118" y="29" width="16" height="6" rx="2"/>
  </g></symbol>
  <symbol id="w-m4" viewBox="0 0 240 90"><g fill="currentColor">
    <path d="M2 24 L12 27 L34 30 L34 50 L12 50 L2 47 Z"/>
    <rect x="34" y="32" width="52" height="10"/>
    <rect x="86" y="25" width="38" height="22" rx="2"/>
    <rect x="96" y="17" width="24" height="8" rx="2"/>
    <rect x="122" y="29" width="52" height="13" rx="3"/>
    <rect x="170" y="32" width="54" height="7"/><rect x="218" y="30" width="11" height="11" rx="2"/>
    <rect x="196" y="18" width="6" height="14"/>
    <path d="M100 47 L122 47 L130 82 L108 80 Z"/>
    <path d="M86 47 L101 47 L96 70 L82 68 Z"/>
    <path d="M104 51 L111 51 L109 59 L103 59 Z"/>
  </g></symbol>
  <symbol id="w-deagle" viewBox="0 0 170 100"><g fill="currentColor">
    <rect x="20" y="32" width="100" height="14" rx="3"/>
    <rect x="112" y="34" width="18" height="12" rx="2"/>
    <rect x="104" y="26" width="6" height="7"/><rect x="30" y="26" width="8" height="7"/>
    <rect x="42" y="46" width="70" height="8" rx="2"/>
    <path d="M66 52 L88 52 L72 96 L52 96 Z"/>
    <path d="M88 52 C104 52 109 60 101 68 L93 66 C97 60 95 56 88 56 Z"/>
    <path d="M94 56 L101 56 L99 65 L93 65 Z"/>
    <path d="M20 30 L32 26 L36 36 L22 38 Z"/>
  </g></symbol>
  <symbol id="w-knife" viewBox="0 0 150 100"><g fill="currentColor">
    <path d="M50 38 C88 46 112 42 128 20 C116 52 88 68 50 64 Z"/>
    <path d="M46 32 L56 64 L32 72 C20 74 14 64 20 54 Z"/>
    <circle cx="18" cy="58" r="9.5" fill="none" stroke="currentColor" stroke-width="4.5"/>
  </g></symbol>
  <symbol id="w-he" viewBox="0 0 110 130"><g fill="currentColor">
    <rect x="24" y="44" width="64" height="78" rx="30"/>
    <rect x="40" y="32" width="30" height="14" rx="4"/>
    <path d="M62 28 L94 12 L98 24 L66 40 Z"/>
    <circle cx="54" cy="15" r="9" fill="none" stroke="currentColor" stroke-width="4.5"/>
  </g></symbol>
  <symbol id="w-flash" viewBox="0 0 110 130"><g fill="currentColor">
    <rect x="30" y="42" width="52" height="80" rx="11"/>
    <rect x="42" y="30" width="28" height="13" rx="3"/>
    <path d="M62 26 L92 11 L96 22 L66 37 Z"/>
    <circle cx="55" cy="14" r="8.5" fill="none" stroke="currentColor" stroke-width="4.5"/>
  </g></symbol>
</svg>"""

ARMS_BG = """<div class="arms" aria-hidden="true">
  <svg class="arm arm-1" viewBox="0 0 240 90"><use href="#w-awp"/></svg>
  <svg class="arm arm-2" viewBox="0 0 240 90"><use href="#w-ak"/></svg>
  <svg class="arm arm-3" viewBox="0 0 240 90"><use href="#w-m4"/></svg>
  <svg class="arm arm-4" viewBox="0 0 170 100"><use href="#w-deagle"/></svg>
  <svg class="arm arm-5" viewBox="0 0 150 100"><use href="#w-knife"/></svg>
  <svg class="arm arm-6" viewBox="0 0 110 130"><use href="#w-he"/></svg>
  <svg class="arm arm-7" viewBox="0 0 110 130"><use href="#w-flash"/></svg>
</div>"""

CORE_JS = r"""
const REPO = '__REPO__';
let D = JSON.parse(document.getElementById('niko-data').textContent);
let FRESH = null;
const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const params = new URLSearchParams(location.search);

function bj(iso){
  if(!iso) return '';
  const d = new Date(iso), p = n => String(n).padStart(2,'0');
  const wk = ['周日','周一','周二','周三','周四','周五','周六'][d.getDay()];
  return `${d.getFullYear()}-${p(d.getMonth()+1)}-${p(d.getDate())} ${wk} ${p(d.getHours())}:${p(d.getMinutes())}`;
}
function boText(bo){ return {Bo1:'单图决胜',Bo3:'三局两胜',Bo5:'五局三胜'}[bo] || bo || ''; }
/* 地图名中文化（保留英文原名，CS 玩家两种叫法都在用） */
const MAP_ZH = {'Dust II':'炙热沙城 II','Mirage':'荒漠迷城','Inferno':'炼狱小镇',
  'Nuke':'核子危机','Ancient':'远古遗迹','Anubis':'阿努比斯神庙',
  'Train':'列车停放站','Overpass':'死亡游乐园','Vertigo':'殒命大厦'};
function mapName(m){
  const zh = MAP_ZH[m];
  return zh ? `${esc(zh)}<span class="map-en">${esc(m)}</span>` : esc(m);
}
function tierText(t){ return String(t||'').replace('S-Tier','S 级').replace('A-Tier','A 级'); }
function ini(id){ return esc(String(id||'?').slice(0,2).toUpperCase()); }

/* 头像：有图用图，无图或加载失败用首两位字母兜底 */
function avatar(src, name, cls){
  const ph = `<div class="av-ph av-ph-${cls}">${ini(name)}</div>`;
  if(!src) return ph;
  // onerror 里的 HTML 必须把双引号转成实体，否则会提前闭合属性
  const fb = ph.replace(/"/g, '&quot;').replace(/\n/g, '');
  return `<img class="av av-${cls}" src="${esc(src)}" alt="${esc(name)}" loading="lazy" decoding="async"
    onerror="this.outerHTML='${fb}'">`;
}
function dataOf(){ return FRESH || D; }

/* ===== 真实地图背景 =====
   每张历史比分里的地图，用「同一张地图」的实景图做背景。
   --mimg  真实高清图（直接内联写死，不依赖 JS，保证一定显示）
   --mlqip 16px 模糊占位图（垫在真图下面，真图没下载完时不闪白） */
const MAP_BG = __MAPBG__;
/* 兜底：万一某张卡是动态插入的，再补一次真图（幂等，不会出错） */
function applyMapBg(el){
  const info = MAP_BG[el.getAttribute('data-map')];
  if(info && info.f && !el.style.getPropertyValue('--mimg'))
    el.style.setProperty('--mimg', "url('" + info.f + "')");
}
function lazyMapBg(){
  const els = document.querySelectorAll('.map.has-bg[data-map]');
  els.forEach(applyMapBg);
}
/* 注意：class 必须并进已有的 class 属性里（HTML 只认第一个 class），
   所以这里只返回 data-map / style，has-bg 由 mapBgCls 追加。 */
function mapBgCls(map){ return MAP_BG[map] ? ' has-bg' : ''; }
function mapBgAttr(map, extraStyle){
  const info = MAP_BG[map];
  if(!info) return extraStyle ? ` style="${extraStyle}"` : '';
  const dm = ` data-map="${esc(map)}"`;
  let s = `--mimg:url('${info.f}');--mlqip:url('${info.l}')`;
  if(extraStyle) s += ';' + extraStyle;
  return dm + ` style="${s}"`;
}

/* 带超时的 fetch：远端源（jsDelivr 等）卡住时 5 秒内放弃，不让页面干等 */
function fetchTO(u, ms){
  const c = new AbortController();
  const t = setTimeout(() => c.abort(), ms || 5000);
  return fetch(u, {cache:'no-store', signal: c.signal}).finally(() => clearTimeout(t));
}

/* ===== 赛事中心数据（含实时刷新） ===== */
let EV = __EVENT__;
let EV_FRESH = null;
function evData(){ return EV_FRESH || EV; }
async function pullEvent(){
  const urls = [['/gh/event.json', 'CF 实时']];
  if(REPO && REPO !== '__REPO__'){
    urls.push(['https://cdn.jsdelivr.net/gh/' + REPO + '@main/event.json', 'jsDelivr']);
    urls.push(['https://raw.githubusercontent.com/' + REPO + '/main/event.json', 'GitHub 直连']);
  }
  urls.push(['./event.json', '同源']);
  for(const [u, tag] of urls){
    try{
      const r = await fetchTO(u + '?t=' + Date.now(), 5000);
      if(!r.ok) continue;
      const d = await r.json();
      // 同样要求「真的有赛事」：空数组 [] 也是 truthy，不能只看真值
      if(d && Array.isArray(d.events) && d.events.length){ return {data:d, tag}; }
    }catch(e){}
  }
  return null;
}

// 赛事数据内容指纹：任一赛事的 brackets/schedule/groups 数量、status、updated 变化都算「变了」。
// 用指纹判断自动刷新，比单看 updated 时间戳更稳健——万一 Actions 重跑时 updated 字段异常没变，
// 只要真实内容变了前端照样重渲染，不会出现「线上已更新但页面不刷新」的僵局。
/* 数据变更指纹：判断「拉回来的远端数据跟当前渲染的是不是同一份」。
   ⚠ 必须覆盖比分与逐图回合。旧实现只比 (场次数, 状态)，比分解构后完全相同——
   比赛从 0:0 打到 2:0、单图从 13 打到 14，场次数和赛事状态都没变，指纹不变，
   render() 于是永远不被调用：后端每 5 分钟提交的新比分根本画不到页面上。
   这是「刷新频率看着低」的前端真凶（2026-10-05 用 _fp_test.js 实证修复）。
   刻意不把 d.updated（整份文件的写入时间）算进来：它每轮都会变，
   会导致每 60 秒无谓重画、滚动位置被顶掉。 */
function eventFingerprint(d){
  const ps = [];
  for(const e of (d.events || [])){
    const br = (e.brackets || []).map(b => (b.rounds || []).map(rd =>
      (rd.matches || []).map(m => [
        m.a && m.a.name, m.a && m.a.score, m.b && m.b.name, m.b && m.b.score,
        (m.maps || []).map(x => (x.a && x.a.rounds) + '-' + (x.b && x.b.rounds)).join(',')
      ].join('/')).join(';')).join('~')).join('||');
    const sc = (e.schedule || []).map(m =>
      [m.a, m.sa, m.b, m.sb].join('/')).join(';');
    ps.push([e.id, e.status, br, sc].join(':'));
  }
  return ps.join('|');
}

/* Liquipedia 改版降级时，event.json 的赛事会带 parse_warning 字段（旧数据已保留）。
   此函数在页面顶部显示固定横幅，让用户一开站点就知道数据可能已过时——
   这是取代「每日轮询巡检」的站内自报机制，无需任何外部定时任务。 */
function renderWarnBanner(){
  let evs = [];
  try { evs = (evData().events || []); } catch(e){ evs = []; }
  const bad = evs.filter(e => e && e.parse_warning);
  let box = document.getElementById('parseWarnBanner');
  if(!bad.length){
    if(box) box.remove();
    return;
  }
  if(!box){
    box = document.createElement('div');
    box.id = 'parseWarnBanner';
    document.body.insertBefore(box, document.body.firstChild);
  }
  const names = bad.map(e => e.name || e.short || e.id).join('、');
  box.textContent = '⚠ 赛事中心部分数据解析异常（疑似 Liquipedia 改版）：当前展示的是最近一次正常抓取的旧数据，可能不是最新。涉及：' + names;
  box.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:9999;background:#b3261e;'
    + 'color:#fff;font:600 13px/1.5 system-ui,-apple-system,sans-serif;padding:8px 14px;'
    + 'text-align:center;box-shadow:0 2px 8px rgba(0,0,0,.35)';
}

/* ===== 官方照片墙数据（可联网更新） ===== */
let PH = __PHOTOS__;
let PH_FRESH = null;
function photosData(){ return PH_FRESH || PH || []; }
async function pullPhotos(){
  const urls = [['/gh/photos.json', 'CF 实时']];
  if(REPO && REPO !== '__REPO__'){
    urls.push(['https://cdn.jsdelivr.net/gh/' + REPO + '@main/photos.json', 'jsDelivr']);
    urls.push(['https://raw.githubusercontent.com/' + REPO + '/main/photos.json', 'GitHub 直连']);
  }
  urls.push(['./photos.json', '同源']);
  for(const [u, tag] of urls){
    try{
      const r = await fetchTO(u + '?t=' + Date.now(), 5000);
      if(!r.ok) continue;
      const d = await r.json();
      if(Array.isArray(d) && d.length){ PH_FRESH = d; return tag; }
    }catch(e){}
  }
  return null;
}

/* ---------- 个人简介文案（NiKo） ---------- */
const NIKO_BIO = '尼科拉·科瓦奇（Nikola Kovač），1997 年 2 月 16 日生于波黑，'
  + '<b>被公认为 CS 历史上最顶尖的步枪手之一</b>。2009 年接触 CS 系列，2013 年踏上职业赛场，'
  + '先后效力 mousesports、FaZe Clan、G2 Esports，2025 年 1 月加盟 Team Falcons。'
  + '2026 年 6 月，他在 IEM 科隆 Major 决赛 <b>3-0 击败 FURIA</b>，拿下职业生涯<b>首个 Major 冠军</b>——'
  + '距他首次打进 Major 决赛已隔 3067 天。生涯 10 次入选 HLTV TOP20、10 次大赛 MVP，总奖金突破 200 万美元。';
/* ===== 照片墙 + 灯箱（首页与选手页共用） ===== */
let CURPH = 0;                 // 灯箱当前索引
function pwItems(){
  const L = photosData();
  return L.map((p, i) => `
    <div class="pw-item" data-i="${i}">
      ${i === 0 ? '<span class="pw-new">最新</span>' : ''}
      <img src="${esc(p.src)}" alt="${esc(p.caption)}" loading="lazy">
      <div class="pw-cap"><b>${esc(p.caption)}</b>
        <span>${p.year ? p.year : '官方照片'}</span></div>
    </div>`).join('');
}
function pwallSec(){
  const L = photosData();
  if(!L.length) return '';
  return `<div class="sec">
    <div class="sec-h"><b>官方照片墙</b><i></i>
      <em>${L.length} 张 · 最近 ${esc(L[0].caption)}</em></div>
    <div class="pwall" id="pwall">${pwItems()}</div>
    <div class="pw-hint">← 左右滑动 · 点按放大 →</div>
  </div>`;
}
function plbHtml(){
  return `<div class="plb" id="plb">
    <span class="plb-x" id="plbX">✕</span>
    <span class="plb-nav l" id="plbL">‹</span>
    <img class="plb-img" id="plbImg" alt="">
    <div class="plb-cap" id="plbCap"></div>
    <span class="plb-nav r" id="plbR">›</span>
  </div>`;
}
function openLb(i){
  const L = photosData(); if(!L.length) return;
  CURPH = (i % L.length + L.length) % L.length;
  const p = L[CURPH];
  const img = document.getElementById('plbImg');
  if(!img) return;
  img.src = p.src; img.alt = p.caption;
  document.getElementById('plbCap').textContent = p.caption + (p.year ? ' · ' + p.year : '');
  document.getElementById('plb').classList.add('on');
}
function closeLb(){
  const e = document.getElementById('plb'); if(e) e.classList.remove('on');
}
/* 保证灯箱存在（放在 body 里，避免被首页的滚动渐显动画影响），并把交互绑好。
   可重复调用：元素级监听只绑一次。 */
let __pwBound = false;
function bindPhotos(){
  const gal = document.getElementById('heroGal');
  if(gal) gal.onclick = () => {
    const w = document.getElementById('pwall');
    if(w) w.scrollIntoView({behavior:'smooth', block:'center'});
  };
  const wall = document.getElementById('pwall');
  if(wall && !wall.dataset.pw){
    wall.dataset.pw = '1';
    wall.addEventListener('click', e => {
      const it = e.target.closest('.pw-item'); if(it) openLb(+it.dataset.i);
    });
  }
  if(!document.getElementById('plb')) document.body.insertAdjacentHTML('beforeend', plbHtml());
  const plb = document.getElementById('plb');
  if(!plb || __pwBound) return;
  __pwBound = true;
  document.getElementById('plbX').onclick = closeLb;
  document.getElementById('plbL').onclick = e => { e.stopPropagation(); openLb(CURPH - 1); };
  document.getElementById('plbR').onclick = e => { e.stopPropagation(); openLb(CURPH + 1); };
  plb.addEventListener('click', e => { if(e.target === plb) closeLb(); });
  document.addEventListener('keydown', e => {
    if(!plb.classList.contains('on')) return;
    if(e.key === 'Escape') closeLb();
    else if(e.key === 'ArrowLeft') openLb(CURPH - 1);
    else if(e.key === 'ArrowRight') openLb(CURPH + 1);
  });
}

/* ===== 赛事中心的通用工具（首页与赛事页共用） ===== */
const ROUND_ZH = {
  'Quarterfinals':'四分之一决赛','Semifinals':'半决赛','Grand Final':'总决赛','Final':'决赛',
  'Upper Bracket Quarterfinals':'胜者组 首轮','Upper Bracket Semifinals':'胜者组 半决赛',
  'Upper Bracket Final':'胜者组 决赛','Lower Bracket Quarterfinals':'败者组 首轮',
  'Lower Bracket Semifinals':'败者组 半决赛','Lower Bracket Final':'败者组 决赛',
  'Round 1':'第 1 轮','Round 2':'第 2 轮','Round 3':'第 3 轮','Round 4':'第 4 轮','Round 5':'第 5 轮',
  'Playoffs':'淘汰赛','Results':'淘汰赛','Group A':'A 组','Group B':'B 组','Group C':'C 组','Group D':'D 组',
  'Group Stage':'小组赛','First Stage':'第一阶段','Swiss Stage':'瑞士轮','Stage 1':'第一阶段','Stage 2':'第二阶段','Stage 3':'第三阶段'
};
function zhRound(n){ return ROUND_ZH[n] || n; }

/* 队名缩写：分支图列宽有限（要一屏放下不右滑），全名太长会挤爆。
   优先用「通用简称」表（CS 观众都认），表里没有再按规则截断。 */
const TEAM_ABBR = {
  'Team Falcons':'FLC','Falcons':'FLC','Natus Vincere':'NAVI','NAVI':'NAVI',
  'BetBoom Team':'BBT','G2 Esports':'G2','Team Vitality':'VIT','Vitality':'VIT',
  'Team Spirit':'SPT','Spirit':'SPT','MOUZ':'MOUZ','Aurora Gaming':'AUR',
  'PARIVISION':'PARI','FURIA':'FURIA','Legacy':'LEG','9z Team':'9Z','1w Team':'1WIN',
  'M80':'M80','TYLOO':'TYLOO','ShindeN':'SHD','GamerLegion':'GL','ENCE':'ENCE',
  'Astralis':'AST','Liquid':'LIQ','Complexity':'COL','FaZe':'FAZE','Virtus.pro':'VP',
  'B8':'B8','SAW':'SAW','The MongolZ':'MONGOLZ','3DMAX':'3DMAX','Aurora':'AUR',
  'G2':'G2','Fnatic':'FNC','Vitality':'VIT','NIP':'NIP','HEROIC':'HEROIC'
};
function abbrTeam(name){
  const n = String(name || '').trim();
  if(!n) return '?';
  if(TEAM_ABBR[n]) return TEAM_ABBR[n];
  // 去掉常见后缀再取首字母缩写：Xxx Esports / Team Xxx / Xxx Gaming
  const base = n.replace(/\s*(Esports|eSports|Gaming|Team)\s*/gi,' ').trim() || n;
  const words = base.split(/[\s\-_]+/).filter(Boolean);
  if(words.length >= 2){
    // 取前两个词的首字母，如 "Bet Boom"->BB
    return (words[0][0] + words[1][0]).toUpperCase();
  }
  return n.slice(0,4).toUpperCase();
}
function isPlayoff(t){ return /playoff|results|final|淘汰/i.test(t || ''); }
/* 队名 -> 队标（容错匹配：忽略大小写/符号，允许 Esports 之类的后缀差异与前缀包含）。
   event.json 里 teams[].logo 是 Liquipedia 下发的队标，路径形如 assets/teams/xxx.png。
   （放在 CORE_JS：首页 hero 与赛事页排行榜都要用） */
function teamLogo(ev, name){
  if(!ev || !name) return '';
  const norm = s => String(s).toLowerCase().replace(/[^a-z0-9]/g, '');
  const n = norm(name);
  if(!n) return '';
  const ts = ev.teams || [];
  let hit = ts.find(t => norm(t.name) === n);
  if(!hit) hit = ts.find(t => { const k = norm(t.name); return k && (k.indexOf(n) === 0 || n.indexOf(k) === 0); });
  return hit ? (hit.logo || '') : '';
}
function bjHM(ts){
  const d = new Date(ts * 1000 + 8 * 3600 * 1000), p = n => String(n).padStart(2, '0');
  return p(d.getUTCHours()) + ':' + p(d.getUTCMinutes());
}
/* 紧凑的「几月几号 几点几分」（分支图卡片用）：如 10/6 00:30 */
function bjShort(ts){
  const d = new Date(ts * 1000 + 8 * 3600 * 1000), p = n => String(n).padStart(2, '0');
  return (d.getUTCMonth() + 1) + '/' + d.getUTCDate() + ' ' + p(d.getUTCHours()) + ':' + p(d.getUTCMinutes());
}
function bjDayLabel(ts){
  const d = new Date(ts * 1000 + 8 * 3600 * 1000);
  return (d.getUTCMonth() + 1) + ' 月 ' + d.getUTCDate() + ' 日 · 周'
    + '日一二三四五六'[d.getUTCDay()];
}
/* 粗略判定「正在打」：开赛时间已过、且仍在 3.2 小时内 */
function isLive(ts){
  if(!ts) return false;
  const now = Date.now() / 1000;
  return ts <= now && now < ts + 3.2 * 3600;
}
function statusCn(s){ return s === 'live' ? '进行中' : s === 'done' ? '已结束' : '即将开始'; }
function statusCls(s){ return s === 'live' ? 's-live' : s === 'done' ? 's-done' : 's-up'; }
/* 赛事状态按时间戳实时算（不信赖服务端烤进 JSON 的 status 字符串）。
   只要 start/end 正确（固定日期，不会过期），无论服务端多久没刷新，
   浏览器每帧都能给出对的『进行中 / 即将开始 / 已结束』——彻底杜绝
   “已经开打却显示即将开始”这类因 JSON 暂未刷新导致的展示错误。
   赛事中心、赛事详情、首页赛事卡全部走这个函数。 */
function liveStatus(start, end){
  if(!start) return 'upcoming';
  const now = Date.now() / 1000;
  const s = Date.parse(start) / 1000;
  if(!Number.isFinite(s)) return 'upcoming';
  const e = end ? Date.parse(end) / 1000 : s + 7 * 86400;
  if(now < s) return 'upcoming';
  if(now <= e) return 'live';
  return 'done';
}
function brkCount(e){ return (e.brackets || []).reduce((a, b) => a + (b.count || 0), 0); }
/* 场次开赛时间戳：优先 m.ts；小组赛（brackets/matchlist）的 m.ts 常为 null，
   但稳定 id 形如 `...__{slug}__{unix_ts}`，末段就是开赛时间，用它兜底
   （2026-10-05：Falcons vs Vitality 的 ts=null，靠 id 才认得出「下一场」）。 */
function matchTs(m){
  if(m && m.ts) return m.ts;
  const id = m && m.id;
  if(id){
    const tail = String(id).split('__').pop();
    const n = parseInt(tail, 10);
    if(Number.isFinite(n) && n > 1e9) return n;   // 1e9≈2001，排除非时间戳尾段
  }
  return null;
}
function featuredEvent(){
  const d = evData(), EVS = d.events || [];
  if(!EVS.length) return null;
  return EVS.find(x => x.id === (d.featured && d.featured.id)) || EVS[0];
}

/* 法尔孔是否还会在某赛事打比赛（仍有未开打 / 进行中的场次）。
   用途：判断「当前已开打的赛事，法尔孔是仍在打还是已经被淘汰出局」。
   被淘汰的当前赛事（已在打、但法尔孔已无下一场）不应再作为首页 hero 的
   「下一站赛事」展示，应直接跳到下一个预告赛事。
   匹配按 short / name / id；抓不到明细时保守返回 false（避免把已淘汰赛事当未来赛事）。 */
function falconsStillIn(t){
  if(!t) return false;
  const EVS = (evData().events || []);
  const e = EVS.find(x => x.short === t.short || x.name === t.name
                        || (t.id && x.id === t.id));
  if(!e) return false;
  const now = Date.now() / 1000;
  const hasUpcoming = (m) => {
    const an = typeof m.a === 'string' ? m.a : (m.a && m.a.name);
    const bn = typeof m.b === 'string' ? m.b : (m.b && m.b.name);
    if(!/falcon/i.test((an || '') + ' ' + (bn || ''))) return false;  // ★ 只要法尔孔
    // 对手待定（b 为空）的 falcons 场也计入：半决赛对手未定时它才是「还有比赛」
    // （2026-10-16 修复：旧逻辑 `if(!an||!bn) return false` 会把 falcons 待定场
    //  误判为「已无下一场」，导致首页 hero 跳过本届、错显「下一站赛事」）
    const ts = matchTs(m);
    return ts && ts >= now;
  };
  for(const m of (e.schedule || [])) if(hasUpcoming(m)) return true;
  for(const b of (e.brackets || [])) for(const rd of (b.rounds || []))
    for(const m of (rd.matches || [])) if(hasUpcoming(m)) return true;
  return false;
}

/* 数据质量分 = 系列赛场次数 + 赛季统计场次数。
   上游定时任务一旦抓取失败，会产出「结构完整但 recent_matches 为空」的
   data.json 并覆盖仓库里的好数据；若照单全收，页面会从有数据瞬间变成全是 0。
   这里给远端数据设下限：低于内置数据 75% 直接丢弃，宁可用内置/旧数据。 */
function dataScore(d){
  if(!d || typeof d !== 'object') return -1;
  if(!Array.isArray(d.recent_matches)) return -1;
  return d.recent_matches.length + (Number((d.year_stats || {}).matches) || 0);
}
async function pullNewest(){
  const urls = [['/gh/data.json', 'CF 实时']];
  if(REPO && REPO !== '__REPO__'){
    urls.push(['https://cdn.jsdelivr.net/gh/' + REPO + '@main/data.json', 'jsDelivr']);
    urls.push(['https://raw.githubusercontent.com/' + REPO + '/main/data.json', 'GitHub 直连']);
  }
  urls.push(['./data.json', '同源']);
  const floor = dataScore(D) * 0.75;        // 容忍小幅修正，拒绝断崖式缺失
  const got = await Promise.all(urls.map(async ([u, tag]) => {
    try{
      const r = await fetchTO(u + '?t=' + Date.now(), 5000);
      if(!r.ok) return null;
      const d = await r.json();
      return { d, tag, sc: dataScore(d) };
    }catch(e){ return null; }
  }));
  let best = null;
  got.forEach(x => {
    if(!x || x.sc <= 0 || x.sc < floor) return;
    if(!best || x.sc > best.sc) best = x;
  });
  if(best){ FRESH = best.d; return best.tag; }
  return null;
}
let __syncSig = '';
async function sync(labelEl){
  const tag = await pullNewest();
  if(labelEl) labelEl.textContent = tag
    ? `● 已同步最新数据（${tag}）`
    : '○ 使用内置数据（远端暂无更新）';
  // 后台拿到更新数据后静默重渲染（数据有实际变化才重画，避免闪烁）
  if(tag && FRESH){
    const up = (FRESH.meta || {}).updated;
    // 页脚时间戳是构建期写死的，数据拉新后同步刷新，否则永远停在最后一次重建的日期
    if(up) document.querySelectorAll('.foot').forEach(el => {
      el.textContent = el.textContent.replace(/最近更新：[\s\S]*$/, '最近更新：' + up);
    });
    const sig = ((FRESH.meta || {}).updated || '') + '|' +
                (FRESH.upcoming_tournaments || []).map(t => [t.short, t.start, t.end, t.date_text].join('=')).join(',') + '|' +
                ((FRESH.recent_matches || []).length);
    if(sig !== __syncSig){
      __syncSig = sig;
      render();
      if(typeof fx === 'function') fx();
    }
  }
  return tag;
}
let __cdTimer = null;
function startCountdown(target, onChange){
  const el = {
    d: document.getElementById('cdD'), h: document.getElementById('cdH'),
    m: document.getElementById('cdM'), s: document.getElementById('cdS')
  };
  if(!el.d) return;
  if(__cdTimer){ clearInterval(__cdTimer); __cdTimer = null; }   // 重渲染前清掉旧定时器，否则倒计时会越跑越快
  const tick = () => {
    let diff = target ? (new Date(target) - Date.now()) / 1000 : 0;
    if(diff < 0) diff = 0;
    const dd = Math.floor(diff / 86400), hh = Math.floor(diff % 86400 / 3600),
          mm = Math.floor(diff % 3600 / 60), ss = Math.floor(diff % 60);
    el.d.textContent = dd; el.h.textContent = String(hh).padStart(2,'0');
    el.m.textContent = String(mm).padStart(2,'0'); el.s.textContent = String(ss).padStart(2,'0');
    const st = document.getElementById('statusTxt'), dot = document.getElementById('dot');
    if(st && diff <= 0){ st.textContent = '进行中'; dot.classList.add('live'); }
    else if(st){ st.textContent = '待战'; }
  };
  tick(); __cdTimer = setInterval(tick, 1000);
}
function drawCrosshair(x, boxId){
  const box = document.getElementById(boxId || 'xhBox');
  if(!box || !x || !x.style) return;
  // 还原 NiKo 游戏内实际准星：经典静态 style 4 / size 1 / gap -4 /
  // 粗细 0 / 无中心点 / 无描边 / 自定义绿 #00FF91。
  // 关键：gap 是【负值】，四根线要交汇重叠在中心，而不是在中间留一道缝隙。
  const U  = 3;                                    // 1 单位 ≈ 3px
  const sz = Number(x.size || 1);
  const gp = Math.min(0, Number(x.gap || 0));      // 只认负值（负=交汇）
  const th = Math.max(2, Number(x.thickness || 0) + 1);
  const R  = Math.max(7, (sz + Math.abs(gp)) * U); // 单臂长度
  const yes = v => v === 'Yes' || v === '是' || v === true;
  const c = document.createElement('div');
  c.style.cssText = 'position:relative;width:0;height:0';
  const bar = (w, h, l, t) => {
    const i = document.createElement('i');
    i.style.cssText = 'width:' + w + 'px;height:' + h + 'px;left:' + l + 'px;top:' + t + 'px';
    c.appendChild(i);
  };
  bar(th, R, -th / 2, -R);      // 上
  bar(th, R, -th / 2, 0);       // 下
  bar(R, th, -R, -th / 2);      // 左
  bar(R, th, 0, -th / 2);       // 右
  if(yes(x.dot)) bar(th, th, -th / 2, -th / 2);   // NiKo 无中心点，此行不会触发
  box.innerHTML = ''; box.appendChild(c);
}



"""



INDEX_JS = CORE_JS + r"""
let LIMIT = 12;
function matchRow(m, maxR){
  const rs = (m.niko && m.niko.ratings) || [];
  const avg = rs.length ? rs.reduce((a,b)=>a+b,0)/rs.length : null;
  return `<a class="row ${m.result}" href="match.html?id=${encodeURIComponent(m.id)}">
    <div class="res ${m.result}">${m.result === 'W' ? '胜' : '负'}</div>
    <div class="sc">${esc(m.score)}</div>
    <div class="info">
      <div class="o">${esc(m.opponent)}</div>
      <div class="e">${esc(m.event)} · ${boText(m.bo)}</div>
    </div>
    <div class="rt">${avg !== null
      ? `<b>${avg.toFixed(2)}</b><small>评分</small>
         <div class="bar"><i style="width:${Math.min(100, avg/maxR*100)}%"></i></div>`
      : `<small style="padding-top:6px" title="评分数据源（HLTV）暂时受限，该场数据待自动回补">—</small>`}</div>
    <div class="chev">›</div>
  </a>`;
}

/* 赛事中心入口：当前/下一站 + 最近赛事 */
function evEntry(){
  const EVS = (evData().events || []);
  if(!EVS.length) return '';
  const cards = EVS.map(e => {
    const n = brkCount(e);
    const all = e.teams || [];
    const lg = all.slice(0, 8).map(t => t.logo
      ? `<img src="${esc(t.logo)}" alt="${esc(t.name)}" title="${esc(t.name)}" loading="lazy">` : '').join('');
    const more = all.length > 8 ? `<span class="ev-e-more">+${all.length - 8}</span>` : '';
    return `<a class="ev-e" href="event.html?id=${encodeURIComponent(e.id)}">
      <div class="ev-e-h"><b>${esc(e.short || e.name)}</b>
        <span class="ev-b ${statusCls(liveStatus(e.start, e.end))}">${statusCn(liveStatus(e.start, e.end))}</span></div>
      <div class="ev-e-m">${esc(e.name)}</div>
      <div class="ev-e-d">${esc(e.date_text || '')} · ${esc(tierText(e.tier))}${e.prize ? ' · ' + esc(e.prize) : ''}</div>
      ${lg ? `<div class="ev-e-lg">${lg}${more}</div>` : ''}
      <div class="ev-e-f"><span>${n ? n + ' 场对阵' : '对阵待公布'}</span><span>${all.length} 支队伍</span></div>
      <div class="ev-e-go">进入赛事中心 ›</div>
    </a>`;
  }).join('');
  return `<div class="sec">
    <div class="sec-h"><b>赛事中心</b><i></i><em>赛程 · 分组 · 分支图 · 实时比分</em></div>
    <div class="ev-list">${cards}</div>
  </div>`;
}

/* 首页 NiKo 资料卡：大图 + 关键数据 + 个人简介 + 官方照片墙 */
function nikoCard(){
  const d = dataOf(), P = d.player, c = P.career || {};
  const L = photosData();
  const photo = L.length ? L[0].src : P.photo;

  const chips = [
    [P.rating_3m.toFixed(2), '近三月评分', true],
    ['#' + P.team_rank, '世界排名', false],
    [esc(c.mvp), '大赛 MVP', false],
    [esc(c.top20), 'TOP20', false],
    [(c.kills || 0).toLocaleString('en-US'), '生涯击杀', false],
    [esc(P.winnings), '生涯奖金', false]
  ].map(([v, k, hl]) =>
    `<div class="chip${hl ? ' hl' : ''}"><b>${v}</b><span>${k}</span></div>`).join('');

  const wall = L.length ? `
    <div class="nwall-h">
      <b>官方照片墙</b>
      <em>${L.length} 张 · ${L[L.length - 1].year}–${L[0].year}</em>
    </div>
    <div class="pwall" id="pwall">${pwItems()}</div>
    <div class="pw-hint">← 左右滑动 · 点按放大 →</div>` : '';

  return `<div class="ncard">
    <div class="nhero">
      <img class="nhero-img" src="${esc(photo)}" alt="NiKo">
      <div class="nhero-scrim"></div>
      <span class="phero-badge"><i class="dot"></i>现役 · ${esc(P.team)}</span>
      ${L.length ? `<span class="phero-gal" id="heroGal">照片墙 ${L.length} 张 ›</span>` : ''}
      <div class="nhero-id">
        <div class="nhero-name">${esc(P.nick)}</div>
        <div class="nhero-full">${esc(P.full_name)}</div>
        <div class="nhero-meta">
          <b>${esc(P.country)}</b><i class="sep"></i><span>${esc(P.role)}</span>
          ${P.age ? `<i class="sep"></i><span>${P.age} 岁</span>` : ''}
          <i class="sep"></i><span>世界排名 <b>#${esc(P.team_rank)}</b></span>
        </div>
      </div>
    </div>
    <div class="ncard-body">
      <div class="pchips">${chips}</div>
      <div class="pbio">
        <div class="pbio-h">个人简介</div>
        <p>${NIKO_BIO}</p>
      </div>
      ${wall}
      <a class="ncard-go" href="player.html?id=${encodeURIComponent(P.nick)}">
        完整资料 · 外设 / 准星 / 荣誉 / 战队经历<span>›</span></a>
    </div>
  </div>`;
}

/* ===== 战绩统计（纯前端从 recent_matches 现算；数据缺失时安全降级） =====
   注：LIST 按时间倒序（最新在前）。所有函数对空数组返回空结果，绝不抛异常。 */
function bjDate(iso, mode){
  const t = Date.parse(iso);
  if(isNaN(t)) return '';
  const s = new Date(t + 8 * 3600 * 1000).toISOString();
  return mode === 'mon' ? s.slice(0, 7) : s.slice(0, 10);
}
function streakOf(list){
  let best = 0, bestL = 0, runW = 0, runL = 0, cur = 0, curType = '';
  list.slice().reverse().forEach(m => {          // 由旧到新
    if(m.result === 'W'){ runW++; runL = 0; if(runW > best) best = runW; cur = runW; curType = 'W'; }
    else { runL++; runW = 0; if(runL > bestL) bestL = runL; cur = runL; curType = 'L'; }
  });
  return { best, bestL, cur, curType };
}
function mapPoolOf(list){
  const agg = {};
  list.forEach(m => (m.maps || []).forEach(x => {
    if(x.vetoed || !x.map) return;
    const a = agg[x.map] = agg[x.map] || { map: x.map, n: 0, w: 0 };
    a.n++; if(x.falcons_win) a.w++;
  }));
  return Object.values(agg)
    .map(a => ({ map: a.map, n: a.n, w: a.w, l: a.n - a.w, rate: a.n ? a.w / a.n * 100 : 0 }))
    .sort((a, b) => b.n - a.n);
}
function monthTrendOf(list){
  const agg = {};
  list.forEach(m => {
    const k = bjDate(m.date, 'mon');
    if(!k) return;
    const a = agg[k] = agg[k] || { key: k, w: 0, l: 0 };
    if(m.result === 'W') a.w++; else a.l++;
  });
  return Object.keys(agg).sort().map(k => ({ key: k, w: agg[k].w, l: agg[k].l, n: agg[k].w + agg[k].l }));
}
function eventBoardOf(list){
  const agg = {};
  list.forEach(m => {
    const k = m.event || '未标注赛事';
    const a = agg[k] = agg[k] || { name: k, n: 0, w: 0 };
    a.n++; if(m.result === 'W') a.w++;
  });
  return Object.values(agg)
    .map(a => ({ name: a.name, n: a.n, w: a.w, l: a.n - a.w, rate: a.n ? a.w / a.n * 100 : 0 }))
    .sort((a, b) => (b.rate - a.rate) || (b.n - a.n));
}
function roundStatsOf(list){
  let rounds = 0, maps = 0, ot = 0;
  list.forEach(m => (m.maps || []).forEach(x => {
    if(x.vetoed) return;
    const f = parseInt((x.falcons || {}).rounds, 10);
    const o = parseInt((x.opponent || {}).rounds, 10);
    if(isNaN(f) || isNaN(o)) return;
    maps++; rounds += f + o; if(f + o > 24) ot++;
  }));
  return { rounds, maps, ot };
}
function num(v, d){ return (v === undefined || v === null || v === '' || isNaN(v)) ? (d || '—') : v; }

/* 近一年战绩 · 仪表盘 */
function yearBoardHtml(LIST, YS){
  if(!LIST.length) return '<div class="empty">数据同步中，稍后自动刷新…</div>';
  const st = streakOf(LIST), mon = monthTrendOf(LIST), rnd = roundStatsOf(LIST);
  const bos = {};
  LIST.forEach(m => { const b = m.bo || '未知赛制'; bos[b] = (bos[b] || 0) + 1; });
  const boTxt = Object.entries(bos).sort((a, b) => b[1] - a[1])
    .map(([k, v]) => `<b>${esc(k)}</b> ${v}`).join(' · ');
  const total = num(YS.matches, LIST.length), rate = num(YS.win_rate, 0);
  const recent = LIST.slice(0, 12).reverse();          // 左旧右新
  const maxN = Math.max.apply(null, mon.map(m => m.n).concat([1]));
  const evC = num(YS.events, 0);
  return `
    <div class="yb">
      <div class="yb-nums">
        <div class="yb-n w"><b>${num(YS.wins, 0)}</b><span>胜</span></div>
        <div class="yb-n l"><b>${num(YS.losses, 0)}</b><span>负</span></div>
        <div class="yb-rate"><b>${rate}%</b><span>胜率</span></div>
      </div>
      <div class="yb-bar"><i style="width:${rate}%"></i><u style="left:calc(${rate}% - 1px)"></u></div>
      <div class="yb-legend"><span>${esc(YS.from) || '—'}</span><span>${total} 场系列赛</span><span>${esc(YS.to) || '—'}</span></div>
      <div class="yb-sub">
        <div class="yb-tag">赛制 ${boTxt}</div>
        <div class="yb-tag">参赛站数 <b>${evC}</b></div>
        <div class="yb-tag">出战地图 <b>${rnd.maps}</b></div>
      </div>
      <div class="yb-blk">
        <div class="yb-h"><b>近期形态</b><em>最近 ${recent.length} 场 · 由旧到新</em></div>
        <div class="yb-form">${recent.map(m =>
          `<div class="ff ${m.result === 'W' ? 'W' : 'L'}" title="${esc(m.date ? bjDate(m.date) : '')} ${esc(m.opponent || '')} ${esc(m.score || '')}">${m.result}</div>`).join('')}</div>
      </div>
      <div class="yk">
        <div class="yk-i"><b class="w">${st.best}</b><span>最长连胜</span></div>
        <div class="yk-i"><b class="l">${st.bestL}</b><span>最长连败</span></div>
        <div class="yk-i"><b class="${st.curType === 'W' ? 'w' : 'l'}">${st.cur}</b>
          <span>当前${st.curType === 'W' ? '连胜' : '连败'}</span></div>
      </div>
      <div class="yb-blk">
        <div class="yb-h"><b>月度走势</b><em>${mon.length} 个比赛月 · 柱高 = 场次</em></div>
        <div class="yb-mon">${mon.map(m => `
          <div class="mo" title="${m.key}：${m.w} 胜 ${m.l} 负">
            <i class="l" style="height:${m.l / maxN * 100}%"></i>
            <i class="w" style="height:${m.w / maxN * 100}%"></i>
          </div>`).join('')}</div>
        <div class="yb-mon-x">${mon.map(m => `<span>${m.key.slice(5)}月</span>`).join('')}</div>
      </div>
    </div>`;
}

/* 赛季概览 · 数据卡 + 地图池 + 分站战绩 */
function seasonBoardHtml(LIST, YS){
  if(!LIST.length) return '<div class="empty">数据同步中，稍后自动刷新…</div>';
  const rnd = roundStatsOf(LIST), pool = mapPoolOf(LIST), evb = eventBoardOf(LIST), st = streakOf(LIST);
  const perEvent = YS.events ? YS.matches / YS.events : 0;
  const perMap = rnd.maps ? rnd.rounds / rnd.maps : 0;
  const cells = [
    ['系列赛总数', num(YS.matches, 0), '近一年全部系列赛', false],
    ['系列赛胜率', num(YS.win_rate, 0) + '%', num(YS.wins, 0) + ' 胜 / ' + num(YS.losses, 0) + ' 负', true],
    ['参赛站数', num(YS.events, 0), '平均每站 ' + perEvent.toFixed(1) + ' 场', false],
    ['出战地图', rnd.maps, '累计 ' + rnd.rounds + ' 回合', false],
    ['单图平均回合', perMap.toFixed(1), '加时局 ' + rnd.ot + ' 张', false],
    ['最佳连胜', st.best, '当前 ' + st.cur + (st.curType === 'W' ? ' 连胜' : ' 连败'), false]
  ];
  const cellHtml = cells.map(([k, v, sub, hl]) =>
    `<div class="st${hl ? ' hl' : ''}"><span>${k}</span><b>${v}</b><div class="st-sub">${sub}</div></div>`).join('');

  const poolHtml = pool.length ? `
    <div class="yb-blk">
      <div class="yb-h"><b>地图池胜率</b><em>${pool.length} 张地图 · 共 ${rnd.maps} 图</em></div>
      <div class="pool">${pool.map(p => `
        <div class="pool-row">
          <div class="pool-n">${esc(p.map)}</div>
          <div class="pool-b"><i style="width:${p.rate}%"></i></div>
          <div class="pool-v"><b>${p.rate.toFixed(0)}%</b> · ${p.n} 场</div>
        </div>`).join('')}</div>
    </div>` : '';

  const evHtml = evb.length ? `
    <div class="yb-blk">
      <div class="yb-h"><b>分站战绩</b><em>共 ${evb.length} 站 · 按胜率排序</em></div>
      <div class="eboard">${evb.map(e => `
        <div class="eb">
          <div class="et">${esc(e.name)}</div>
          <div class="er"><b>${e.rate.toFixed(0)}%</b><em>${e.w}胜${e.l}负 · ${e.n} 场</em></div>
          <div class="ebar"><i class="${e.rate < 50 ? 'low' : ''}" style="width:${e.rate}%"></i></div>
        </div>`).join('')}</div>
      <div class="hint">← 左右滑动查看全部 ${evb.length} 站 →</div>
    </div>` : '';

  return `<div class="grid">${cellHtml}</div>${poolHtml}${evHtml}`;
}

/* 首屏 hero 的「下一场比赛」：**只显示法尔孔（NiKo 战队）的比赛**，其他队伍一律不显示
   （2026-10-05 按需求收紧：以前会回退到「其他队伍最近一场」，现在没有法尔孔比赛就返回
   null，由 render() 落到「待公布 / 什么大赛」的模糊占位）。
   选取规则：正在进行的 > 最近一场未开打的。数据源 event.json（每 60 秒同步），
   同时扫 schedule 与 brackets 两个来源——小组赛那场（Falcons vs Vitality）只在
   brackets 里且 ts=null，靠 matchTs() 从 id 取时间才能认出来。 */
function liveFixture(){
  const EVS = (((evData && evData()) || {}).events) || [];
  const now = Date.now() / 1000;
  const cand = [];
  // 把 schedule（扁平对阵，a/b 是字符串）与 brackets（matchlist/bracket，a/b 是对象）
  // 统一成 {a,b,sa,sb,ts,bo,round,id}，供 hero 渲染直接用。
  const collect = (e, m, roundName) => {
    let an = typeof m.a === 'string' ? m.a : (m.a && m.a.name);
    let bn = typeof m.b === 'string' ? m.b : (m.b && m.b.name);
    an = an || ''; bn = bn || '';
    if(/^\s*$/.test(an) && /^\s*$/.test(bn)) return;            // 双方都空才跳过
    if(!/falcon/i.test(an + ' ' + bn)) return;                  // ★ 只要法尔孔
    // 关键修复（2026-10-16）：法尔孔的下一场常「对手待定」（如半决赛对手要看
    // 另一场结果才定，Liquipedia 上 b 为空）。旧逻辑 `if(!an||!bn) return`
    // 把这种场直接丢弃，导致 falcons 的下一场永远进不了 hero，首页只能退而
    // 显示「下一站赛事」（下一个锦标赛）。现在：对手待定也收录，记为 TBD。
    if(/^tbd$/i.test(an) || /^tbd$/i.test(bn)) return;
    const ts = matchTs(m);
    if(!ts) return;
    const sa = typeof m.a === 'string' ? m.sa : (m.a && m.a.score);
    const sb = typeof m.b === 'string' ? m.sb : (m.b && m.b.score);
    const nm = { a: an || 'TBD', b: bn || 'TBD',
                 sa: (sa === undefined ? null : sa), sb: (sb === undefined ? null : sb),
                 ts, bo: m.bo || '', round: roundName || m.round || m.stage || '', id: m.id || '' };
    if(isLive(ts)) cand.push({ pri: 0, e, m: nm, ts, playing: true });
    else if(ts > now) cand.push({ pri: 1, e, m: nm, ts, playing: false });
  };
  EVS.forEach(e => {
    (e.schedule || []).forEach(m => collect(e, m, m.round));
    (e.brackets || []).forEach(b => (b.rounds || []).forEach(rd =>
      (rd.matches || []).forEach(m => collect(e, m, rd.name))));
  });
  if(!cand.length) return null;
  cand.sort((x, y) => x.pri - y.pri || x.ts - y.ts);
  return cand[0];
}

function render(){
  const d = dataOf(), P = d.player, YS = d.year_stats, LIST = d.recent_matches, SQ = d.squad || [];
  const c = P.career || {}, g = P.gear || {}, x = P.crosshair || {};
  const maxR = Math.max(...LIST.flatMap(m => (m.niko && m.niko.ratings) || [0]), 1);

  let heroTag, heroInner, target = null;
  // ① 下一场比赛（赛事中心的实时赛程：进行中 > 最近未开打；同级优先 Falcons 参赛）
  const LF = (typeof liveFixture === 'function') ? liveFixture() : null;
  if(LF){
    const m = LF.m, ev = LF.e, playing = !!LF.playing;
    const hasScore = m.sa !== null && m.sb !== null && m.sa !== undefined;
    heroTag = playing ? (hasScore ? '正在进行' : '即将开始') : '下一场比赛';
    target = new Date(m.ts * 1000).toISOString();
    // 双方队标（取不到时用队名首字母占位）
    const side = name => {
      const isTBD = !name || /^tbd$/i.test(name);   // 对手待定（半决赛对手未定）
      const disp = isTBD ? '待定' : name;
      const lg = isTBD ? '' : teamLogo(ev, name);
      return '<div class="hero-team">'
        + (lg ? `<img src="${esc(lg)}" alt="" loading="lazy">`
              : `<i class="hero-logo-ph">${esc(isTBD ? '?' : ini(name))}</i>`)
        + `<b>${esc(disp)}</b></div>`;
    };
    const mid = hasScore ? (m.sa + ':' + m.sb) : 'VS';
    const meta = [esc(ev.name), esc(m.round || '小组赛'), esc(boText(m.bo))].filter(Boolean).join(' · ');
    heroInner = `<div class="vs">${side(m.a)}
      <div class="vs-mid">${esc(mid)}</div>
      ${side(m.b)}</div>
      <div class="hero-sub">${meta}</div>
      ${playing ? '<div class="hero-note">LIVE 正在进行</div>'
                : '<div class="hero-note">距本场开赛</div>'}`;
  }else if(d.next_match){
    heroTag = '下一场比赛'; target = d.next_match.datetime;
    heroInner = `<div class="vs"><div class="team">FALCONS</div><div class="vs-mid">VS</div>
      <div class="team">${esc(d.next_match.opponent)}</div></div>
      <div class="hero-sub">${esc(d.next_match.event)} · ${boText(d.next_match.bo)}</div>`;
  }else if((d.upcoming_tournaments||[]).length){
    // 跳过「已开打但法尔孔已被淘汰（无下一场）」的当前赛事，直接展示下一个预告赛事
    const U = (d.upcoming_tournaments||[]).slice().sort((a,b)=>Date.parse(a.start)-Date.parse(b.start));
    let ti = -1;
    for(let i = 0; i < U.length; i++){
      const t0 = Date.parse(U[i].start);
      const alreadyOn = Number.isFinite(t0) && t0 <= Date.now();
      if(alreadyOn && !falconsStillIn(U[i])) continue;   // 本届已开打且法尔孔已出局 → 跳过看下一个
      ti = i; break;
    }
    if(ti < 0) ti = 0;                                    // 兜底：全跳过时仍显示第一项
    const t = U[ti];
    const t0 = Date.parse(t.start);
    const alreadyOn = Number.isFinite(t0) && t0 <= Date.now();
    heroTag = alreadyOn ? '赛事进行中' : '下一站赛事'; target = t.start;
    heroInner = `<div class="vs"><div class="team">${esc(t.name)}</div></div>
      <div class="hero-sub">${esc(t.date_text)} · ${tierText(t.tier)}</div>
      <div class="hero-note">${alreadyOn ? '本轮进行中 · 下一场对阵待公布'
                                        : '对阵尚未公布 · 已确认参赛'}</div>`;
  }else{
    heroTag = '暂无赛程';
    heroInner = `<div class="vs"><div class="team tbd">待定</div></div>
      <div class="hero-sub">暂时没有已公布的比赛</div>`;
  }

  // 下一站赛事提示：当前 hero 赛事（下一场比赛所属锦标赛）之后的下一个锦标赛。
  // 这样「下一站赛事」在首屏 hero 内也能看到，不再被「下一场比赛」挤掉
  // （用户曾问「下一站赛事去哪了」——它一直都在下方「未来赛程」列表，这里补个明示）。
  const UforNext = (d.upcoming_tournaments||[]).slice().sort((a,b)=>Date.parse(a.start)-Date.parse(b.start));
  const _curEnd = (LF && LF.e && LF.e.end) ? Date.parse(LF.e.end)
                : (d.featured && d.featured.end ? Date.parse(d.featured.end) : Date.now());
  const _next = UforNext.find(t => Date.parse(t.start) > _curEnd) || null;
  if(_next){
    heroInner += `<div style="margin-top:12px;font-family:var(--mono);font-size:12px;`
      + `color:rgba(255,255,255,.82);letter-spacing:.04em">下一站赛事：`
      + `<b style="color:#fff">${esc(_next.name)}</b> `
      + `<span style="opacity:.75">· ${esc(_next.date_text)} · ${tierText(_next.tier)}</span></div>`;
  }

  const Uall = (d.upcoming_tournaments||[]).slice().sort((a,b)=>Date.parse(a.start)-Date.parse(b.start));
  // 与 hero 保持一致：跳过「已开打且法尔孔已淘汰」的当前赛事
  const Ushown = Uall.filter(t => {
    const t0 = Date.parse(t.start);
    const alreadyOn = Number.isFinite(t0) && t0 <= Date.now();
    return !(alreadyOn && !falconsStillIn(t));
  });
  const upHtml = Ushown.map(t => `
    <div class="up-c">
      <div class="tier">${tierText(t.tier)}</div>
      <div class="n">${esc(t.name)}</div>
      <div class="d">${esc(t.date_text)}</div>
      <div class="m">${new Date(t.start).getUTCFullYear()} 年 · 已确认参赛</div>
    </div>`).join('') || '<div class="empty">暂无已公布赛程</div>';

  const shown = LIST.slice(0, LIMIT);
  const btn = LIST.length > LIMIT
    ? `<button class="more" id="moreBtn">展开全部 ${LIST.length} 场</button>` : '';
  const mates = SQ.filter(p => p.role !== '教练');
  const mateHtml = mates.map(p => `
    <a class="pc" href="player.html?id=${encodeURIComponent(p.id)}">
      <div class="pc-ph">
        ${p.photo ? `<img src="${esc(p.photo)}" alt="${esc(p.id)}" loading="lazy">`
                  : `<div class="pc-ph-txt">${esc(ini(p.id))}</div>`}
        <span class="pc-id">${esc(p.id)}</span>
      </div>
      <div class="pc-meta">
        <div class="prole">${esc(p.role)}</div>
        <div class="pnat">${esc(p.nationality)}${p.age ? ' · ' + p.age + '岁' : ''}</div>
      </div>
    </a>`).join('');

  const stats = [
    ['近三个月评分', P.rating_3m.toFixed(2), true],
    ['世界排名', '#' + P.team_rank, false],
    ['近三个月图数', P.maps_3m, false],
    ['生涯击杀', (c.kills||0).toLocaleString('en-US'), false],
    ['生涯 K/D', (c.kd||0).toFixed(2), false],
    ['生涯 ADR', c.adr, false],
    ['爆头率', (c.hs||0) + '%', false],
    ['生涯 MVP', c.mvp, false],
    ['TOP20 次数', c.top20, false],
    ['生涯奖金', P.winnings, false],
  ].map(([k,v,hl]) => `<div class="st${hl?' hl':''}"><span>${k}</span><b>${v}</b></div>`).join('');

  const mj = P.major || {};
  const majorHtml = mj.title ? `
    <div class="st hl" style="grid-column:1/-1">
      <span>MAJOR 冠军</span>
      <b style="font-size:15px">${esc(mj.title)}</b>
      <div class="st-sub">${esc(mj.date||'')} ${esc(mj.result||'')}</div>
    </div>` : '';

  const gearRows = Object.entries({
    '鼠标': g.mouse, '鼠标垫': g.mousepad, '游戏内灵敏度': g.sens, 'DPI': g.dpi,
    'eDPI': g.edpi, '轮询率': g.polling, '显示器': g.monitor, '刷新率': g.refresh,
    '分辨率': g.resolution, '键盘': g.keyboard, '耳机': g.headset
  }).filter(([,v]) => v).map(([k,v]) =>
    `<div class="kv-row"><span>${k}</span><b>${esc(v)}</b></div>`).join('');

  const xHtml = x.style ? `
    <div class="xh" id="xhBox"></div>
    <div class="kv" style="margin-top:10px">
      <div class="kv-row"><span>参数</span><b>样式 ${esc(x.style)} · 长度 ${esc(x.size)} · 粗细 ${esc(x.thickness)} · 间隙 ${esc(x.gap)}</b></div>
      <div class="kv-row"><span>颜色</span><b><i style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#00FF91;vertical-align:middle;margin-right:6px"></i>自定义绿 #00FF91${(x.outline==='No'||x.outline==='否')?' · 无描边':''}${(x.dot==='No'||x.dot==='否')?' · 无中心点':''}</b></div>
      <div class="kv-row"><span>分享码</span><b style="font-family:var(--mono);font-size:11px">${esc(P.crosshair_sharecode||'—')}</b></div>
    </div>` : '<div class="empty">暂无准星数据</div>';

  const FE = featuredEvent();
  // hero 卡片点击直达「下一场比赛」所属赛事的赛事中心（没有具体对阵时回退到推荐赛事）
  const heroEv = (typeof LF !== 'undefined' && LF) ? LF.e : FE;
  const heroOpen = heroEv
    ? `<a class="hero hero-link" href="event.html?id=${encodeURIComponent(heroEv.id)}">`
    : '<div class="hero">';
  const heroClose = heroEv ? '</a>' : '</div>';

  const rc = LIST.filter(m => ((m.niko || {}).ratings || []).length).length;
  const rateNote = rc < LIST.length
    ? '<div class="hint" style="margin-top:8px">评分来源 HLTV 2.1 · 已收录 ' + rc + '/' + LIST.length + ' 场 · 缺失场次由数据管线自动回补</div>'
    : '';
  document.getElementById('app').innerHTML = `
  ${heroOpen}
    <div class="hero-top"><span class="tag">${heroTag}</span></div>
    <div class="hero-body">
      ${heroInner}
      <div class="cd">
        <div><b id="cdD">--</b><span>天</span></div>
        <div><b id="cdH">--</b><span>时</span></div>
        <div><b id="cdM">--</b><span>分</span></div>
        <div><b id="cdS">--</b><span>秒</span></div>
      </div>
      <div class="hero-sub">${target ? '开赛（北京时间）：' + bj(target) : ''}</div>
      ${FE ? `<div class="hero-cta">进入赛事中心 · 赛程 / 分组 / 分支图<span>›</span></div>` : ''}
    </div>
  ${heroClose}

  ${nikoCard()}

  ${evEntry()}

  <div class="sec">
    <div class="sec-h"><b>现役队友</b><i></i><a href="team.html"><em>查看队伍 ›</em></a></div>
    <div class="hint">← 左右滑动查看全部 ${mates.length} 人 →</div>
    <div class="scroller">${mateHtml}</div>
  </div>

  <div class="sec">
    <div class="sec-h"><b>未来赛程</b><i></i><em>${Ushown.length} 项赛事</em></div>
    <div class="up">${upHtml}</div>
  </div>

  <div class="sec">
    <div class="sec-h"><b>${esc(YS.span)}战绩</b><i></i><em>${YS.wins} 胜 ${YS.losses} 负</em></div>
    ${yearBoardHtml(LIST, YS)}
    <div class="hint" style="margin:15px 0 10px">逐场系列赛比分（点任意一场看逐图详情）</div>
    <div class="rows" id="recList">${shown.map(m => matchRow(m, maxR)).join('')}${btn}</div>
    ${rateNote}
  </div>

  <div class="sec">
    <div class="sec-h"><b>赛季概览</b><i></i><em>${esc(YS.from)} 至 ${esc(YS.to)}</em></div>
    ${seasonBoardHtml(LIST, YS)}
  </div>

  <div class="sec">
    <div class="sec-h"><b>选手数据</b><i></i><em>来源 HLTV</em></div>
    <div class="grid">${stats}${majorHtml}</div>
  </div>

  <div class="sec">
    <div class="sec-h"><b>外设与设置</b><i></i><em>来源 Liquipedia</em></div>
    <div class="kv">${gearRows || '<div class="empty">暂无数据</div>'}</div>
  </div>

  <div class="sec">
    <div class="sec-h"><b>准星</b><i></i><em>${P.crosshair_sharecode?'含分享码':''}</em></div>
    ${xHtml}
  </div>

  <div class="syncbar">
    <span id="liveStatus">○ 正在获取最新数据…</span>
    <button class="lk" id="refreshBtn" style="cursor:pointer">↻ 刷新</button>
  </div>
  <div class="foot">
    数据来源：Liquipedia Counter-Strike Wiki（CC BY-SA 3.0）· HLTV.org<br>
    时间均已换算为北京时间（UTC+8）；个人评分仅覆盖已逐场核对的比赛，其余显示「—」。<br>
    点任意一场比赛可看逐图详情。最近更新：__UPDATED__
  </div>`;

  drawCrosshair(x);
  startCountdown(target);
  const mb = document.getElementById('moreBtn');
  if(mb) mb.onclick = () => {
    const all = LIST.length;
    LIMIT = LIMIT >= all ? 12 : all;
    render();
    sync(document.getElementById('liveStatus'));
  };
  const rb = document.getElementById('refreshBtn');
  if(rb) rb.onclick = async () => {
    document.getElementById('liveStatus').textContent = '○ 正在刷新…';
    const tag = await pullNewest();
    render();
    sync(document.getElementById('liveStatus'));
  };
  bindPhotos();
}

/* ===== 视觉增强：武器背景 / 点击反馈 / 过渡动画 ===== */
const TAP_SEL = 'a,button,.row,.pc,.tc,.lk,.more,.up-c,.st,.map,.prof,.hero';
const SVGNS = 'http://www.w3.org/2000/svg';
const NO_ANIM = matchMedia('(prefers-reduced-motion: reduce)').matches;

/* hero 卡片里放一把 AWP 水印 */
function fxArms(){
  document.querySelectorAll('.hero').forEach(h => {
    if(h.querySelector('.hero-arms')) return;
    const s = document.createElementNS(SVGNS, 'svg');
    s.setAttribute('class', 'hero-arms');
    s.setAttribute('viewBox', '0 0 240 90');
    s.setAttribute('aria-hidden', 'true');
    const u = document.createElementNS(SVGNS, 'use');
    u.setAttribute('href', '#w-awp');
    s.appendChild(u); h.appendChild(s);
  });
}
/* 滚动渐显（逐块错峰） */
function fxReveal(){
  const els = document.querySelectorAll('#app > *');
  if(!els.length) return;
  if(NO_ANIM || !('IntersectionObserver' in window)){
    els.forEach(e => { e.classList.add('rv','in'); }); return;
  }
  const io = new IntersectionObserver(ents => {
    ents.forEach(en => {
      if(en.isIntersecting){ en.target.classList.add('in'); io.unobserve(en.target); }
    });
  }, {rootMargin:'0px 0px -6% 0px', threshold:.03});
  let i = 0;
  els.forEach(e => {
    e.classList.add('rv');
    e.style.setProperty('--rd', (Math.min(i, 5) * 0.07) + 's'); i++;
    io.observe(e);
  });
}
/* 点击 = 涟漪 + CS 命中标记 + 按压回弹（含 iOS 兜底） */
function fxRipple(){
  const release = () => document.querySelectorAll('.pressed')
    .forEach(e => e.classList.remove('pressed'));
  document.addEventListener('pointerup', release, {passive:true});
  document.addEventListener('pointercancel', release, {passive:true});
  window.addEventListener('blur', release);
  document.addEventListener('pointerdown', e => {
    const t = e.target.closest ? e.target.closest(TAP_SEL) : null;
    if(!t) return;
    t.classList.add('pressed');
    setTimeout(() => t.classList.remove('pressed'), 320);
    if(NO_ANIM) return;
    const r = t.getBoundingClientRect();
    const x = e.clientX - r.left, y = e.clientY - r.top;
    const size = Math.max(r.width, r.height) * 1.1;
    const sp = document.createElement('span');
    sp.className = 'ripple';
    sp.style.cssText = 'width:' + size + 'px;height:' + size + 'px;left:'
      + (x - size / 2) + 'px;top:' + (y - size / 2) + 'px';
    const hm = document.createElement('i');
    hm.className = 'hitmark';
    hm.style.cssText = 'left:' + x + 'px;top:' + y + 'px';
    t.appendChild(sp); t.appendChild(hm);
    setTimeout(() => { sp.remove(); hm.remove(); }, 640);
  }, {passive:true});
}
/* 武器层轻微视差 */
function fxParallax(){
  const arms = document.querySelector('.arms');
  if(!arms || NO_ANIM) return;
  let raf = 0;
  addEventListener('scroll', () => {
    if(raf) return;
    raf = requestAnimationFrame(() => {
      raf = 0;
      arms.style.setProperty('--sy', (scrollY * -0.035).toFixed(1) + 'px');
    });
  }, {passive:true});
}
/* 站内跳转反馈（关键：绝不拦截默认行为 / 不用 location.href 程序化跳转）
   原因 1：e.preventDefault() 后再 location.href 跳转，iOS Safari / Android Chrome
   不会把上一页放进「滑动返回」历史栈，导致手机端右滑无法回退到一级页面。
   原因 2：跳转前加的 .leaving 淡出态会被 bfcache（往返缓存）一并记住——右滑返回时
   上一页以 opacity:0 的状态恢复，整个内容区「隐形」，看起来同样是「右滑回不去」。
   所以必须在 pagehide / pageshow 时清掉 .leaving，保证 bfcache 快照是干净状态。 */
function fxLeave(){
  addEventListener('pagehide', () => document.body.classList.remove('leaving'));
  addEventListener('pageshow', () => document.body.classList.remove('leaving'));
  document.addEventListener('click', e => {
    if(e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    const a = e.target.closest ? e.target.closest('a[href]') : null;
    if(!a || a.target === '_blank' || a.hasAttribute('download')) return;
    const href = a.getAttribute('href') || '';
    if(/^(https?:)?\/\//i.test(href) && new URL(href, location.href).origin !== location.origin) return;
    const u = new URL(href, location.href);
    // 同页锚点：交给浏览器原生滚动，不拦截
    if(u.pathname.split('/').pop() === location.pathname.split('/').pop() && u.hash) return;
    // 跨页跳转：仅做淡出反馈，立即放行原生导航（保证右滑返回历史栈正确）
    document.body.classList.add('leaving');
    // 兜底：导航被环境拦下（离线等）时 3 秒后自动恢复，避免页面永久淡出
    setTimeout(() => document.body.classList.remove('leaving'), 3000);
  }, true);
}
let __fxBound = false;
function fx(){
  fxArms(); fxReveal();
  if(__fxBound) return;
  __fxBound = true;
  fxRipple(); fxParallax(); fxLeave();
  const app = document.getElementById('app');
  if(app && 'MutationObserver' in window){
    let t = 0;
    new MutationObserver(() => {
      clearTimeout(t); t = setTimeout(() => { fxArms(); fxReveal(); }, 30);
    }).observe(app, {childList:true});
  }
  /* 兜底：2.5 秒后还没显形的一律显示，避免任何情况下白屏 */
  setTimeout(() => document.querySelectorAll('.rv:not(.in)')
    .forEach(e => e.classList.add('in')), 2500);
}

async function boot(){
  /* 秒开：先用页面内置数据渲染，再后台同步远端（照片/数据到了才重画） */
  render();
  fx();
  const st = document.getElementById('liveStatus');
  sync(st);
  setInterval(() => sync(st), 60000);   // 远端开赛时间/赛程等一旦变动，首页自动刷新（与二级页一致），无需手动点刷新

  /* 赛事（event.json）同步：首屏 hero 的「正在进行 / 下一场」与实时比分要跟着走。
     内置数据是构建时快照，不同步的话开赛后 hero 会一直停在旧状态。 */
  let _evFp = eventFingerprint(evData());
  const evSync = async () => {
    const r = await pullEvent();
    if(!r) return;                       // 联网失败就保留上次数据，下轮再试
    EV_FRESH = r.data;
    const fp = eventFingerprint(r.data);
    if(fp !== _evFp){ _evFp = fp; render(); fx(); }
  };
  evSync();
  setInterval(evSync, 60000);

  pullPhotos().then(tag => {
    if(tag){ render(); fx(); if(st) st.textContent = '● 照片已更新（' + tag + '）'; }
  });
}
"""

MATCH_JS = CORE_JS + r"""
function nk(s){ return (s||'').toLowerCase().replace(/[^a-z0-9]/g,''); }

/* unix 秒 -> 北京时间文本（与站内赛程一致，+8h 取 UTC 字段） */
function tsToDate(ts){
  if(!ts) return '';
  const d = new Date(ts*1000 + 8*3600*1000);
  const p = n => String(n).padStart(2,'0');
  const wk = ['周日','周一','周二','周三','周四','周五','周六'][d.getUTCDay()];
  return d.getUTCFullYear()+'-'+p(d.getUTCMonth()+1)+'-'+p(d.getUTCDate())+' '+wk+' '+p(d.getUTCHours())+':'+p(d.getUTCMinutes());
}

/* 数据源 A：data.json 的近期比赛（NiKo/Falcons 视角） */
function fromRecent(m){
  const parts = String(m.score||'0-0').split('-');
  const sa = parseInt(parts[0],10), sb = parseInt(parts[1],10);
  const maps = (m.maps||[]).map(p => ({
    map: p.map, vetoed: !!p.vetoed,
    a_win: !!p.falcons_win,
    a: {rounds: p.falcons.rounds, t: p.falcons.t, ct: p.falcons.ct},
    b: {rounds: p.opponent.rounds, t: p.opponent.t, ct: p.opponent.ct}
  }));
  return {
    source:'recent',
    a:{name:'FALCONS', score: sa, win: m.result==='W'},
    b:{name: m.opponent, score: sb, win: m.result==='L'},
    scoreText: m.score||'—',
    bo: m.bo, event: m.event, stage: m.stage, dateText: bj(m.date),
    ts: m.date ? Date.parse(m.date)/1000 : null,
    maps, links: m.links||{}, niko: m.niko||null, isNiko: true
  };
}

/* 数据源 B：event.json 的赛事对阵（通用两队伍视角，兼容 bracket 与 schedule 两种结构） */
function evMatchToR(m, ev){
  let an, bn, ascore, bscore, awin, bwin;
  if(typeof m.a === 'string'){
    an = m.a; bn = m.b; ascore = m.sa; bscore = m.sb;
    const played = ascore!=null && bscore!=null;
    awin = played && ascore>bscore; bwin = played && bscore>ascore;
  } else {
    an = m.a.name; bn = m.b.name;
    ascore = m.a.score; bscore = m.b.score;
    awin = !!m.a.win; bwin = !!m.b.win;
  }
  const isN = /falcon/i.test(an + ' ' + bn);
  const maps = (m.maps||[]).map(p => ({
    map: p.map, vetoed: !!p.vetoed,
    a_win: p.a_win,
    a: {rounds: p.a.rounds, t: p.a.t, ct: p.a.ct},
    b: {rounds: p.b.rounds, t: p.b.t, ct: p.b.ct}
  }));
  const scoreText = (ascore!=null && bscore!=null) ? (ascore+':'+bscore) : '—';
  return {
    source:'event',
    a:{name: an, score: ascore, win: awin},
    b:{name: bn, score: bscore, win: bwin},
    scoreText, bo: m.bo, event: ev.name, stage: (m.stage||''),
    dateText: m.ts ? tsToDate(m.ts) : '',
    ts: m.ts || null,
    maps, links: m.links||{}, niko: null, isNiko: isN
  };
}

/* 按 id 查找：先 recent_matches，再遍历 event.json 所有赛事 */
function findMatch(id){
  const d = dataOf();
  const r = (d.recent_matches||[]).find(x => x.id === id);
  if(r) return fromRecent(r);
  for(const ev of (evData().events||[])){
    for(const b of (ev.brackets||[])) for(const rd of b.rounds)
      for(const m of rd.matches) if(m.id === id) return evMatchToR(m, ev);
    for(const m of (ev.schedule||[])) if(m.id === id) return evMatchToR(m, ev);
  }
  return null;
}

function render(){
  const id = params.get('id');
  const R = id ? findMatch(id) : null;
  const app = document.getElementById('app');
  if(!R){
    app.innerHTML = `<div class="back"><a class="lk" href="index.html">‹ 返回</a></div>
      <div class="empty" style="margin-top:30px">找不到这场比赛<br><br>
      <a class="lk" href="index.html">返回首页</a></div>`;
    return;
  }
  const d = dataOf();
  const played = (R.maps||[]).filter(p => !p.vetoed);
  const vetoed = (R.maps||[]).filter(p => p.vetoed);
  const rs = (R.niko && R.niko.ratings) || [];
  const avg = rs.length ? rs.reduce((a,b)=>a+b,0)/rs.length : null;
  const aIsNiko = R.isNiko && /falcon/i.test(R.a.name);
  const bIsNiko = R.isNiko && /falcon/i.test(R.b.name);
  const aLabel = aIsNiko ? d.player.nick : R.a.name;
  const bLabel = bIsNiko ? d.player.nick : R.b.name;
  const nikoWon = R.isNiko ? (aIsNiko ? R.a.win : R.b.win) : null;
  /* 状态按时间戳实时判定（与 liveStatus 同一思路），不再「无比分=即将开始」：
     开赛时间已过但无比分 = 进行中（Liquipedia 尚未录分，2026-10-15 用户实测
     TWC 9z vs Falcons 已开打 1 小时却显示「即将开始」就是这个判断导致的）；
     有比分且系列赛已分出胜负 = 取胜/落败/已结束；有比分未分胜负 = 进行中。
     ts 缺失（纯 bracket TBD 项）时退回比分判断。 */
  const _hasScore = R.a.score != null && R.b.score != null;
  const _seriesDone = _hasScore && (R.a.win || R.b.win);
  let outcome;
  if(R.ts){
    if(!_hasScore) outcome = Date.now()/1000 < R.ts ? '即将开始' : '进行中';
    else if(_seriesDone) outcome = R.isNiko ? (nikoWon ? '取胜' : '落败') : '已结束';
    else outcome = '进行中';
  } else {
    outcome = !_hasScore ? '即将开始'
      : (R.isNiko ? (nikoWon ? '取胜' : '落败') : '已结束');
  }

  const maxRound = Math.max(...played.map(p =>
    Math.max(Number(p.a.rounds)||0, Number(p.b.rounds)||0)), 13);

  const mapHtml = played.map((p, i) => {
    const aw = p.a_win === true;
    const al = p.a_win === false;
    const ar = Number(p.a.rounds)||0, br = Number(p.b.rounds)||0;
    const awc = aw ? 'W' : (al ? 'L' : '');
    const awt = aw ? '胜' : (al ? '负' : '—');
    return `<div class="map ${awc}${mapBgCls(p.map)}"${mapBgAttr(p.map)}>
      <span class="mbg-en">${esc(p.map)}</span>
      <div class="map-h">
        <b>第 ${i+1} 图 · ${mapName(p.map)}</b>
        <em>${ar + br > 24 ? '加时 · ' : ''}共 ${ar + br} 回合</em>
        <div class="map-res ${awc}">${awt} ${ar}-${br}</div>
      </div>
      <div class="mline ${awc?'':'L'}">
        <div class="who">${esc(aLabel)}</div>
        <div class="rounds">${ar}</div>
        <div class="tbar"><i style="width:${Math.min(100, ar/maxRound*100)}%"></i></div>
        <div class="halves">进攻 ${esc(p.a.t)||'—'} / 防守 ${esc(p.a.ct)||'—'}</div>
      </div>
      <div class="mline ${awc?'L':''}">
        <div class="who">${esc(bLabel)}</div>
        <div class="rounds">${br}</div>
        <div class="tbar"><i style="width:${Math.min(100, br/maxRound*100)}%"></i></div>
        <div class="halves">进攻 ${esc(p.b.t)||'—'} / 防守 ${esc(p.b.ct)||'—'}</div>
      </div>
    </div>`;
  }).join('') || '<div class="empty">暂无逐图数据</div>';

  const vetoHtml = vetoed.length ? `
    <div class="sec">
      <div class="sec-h"><b>未选用地图</b><i></i><em>双方已禁用</em></div>
      <div class="rows">${vetoed.map(p => `
        <div class="map veto${mapBgCls(p.map)}"${mapBgAttr(p.map, 'margin-bottom:0')}>
          <div class="map-h"><b>${mapName(p.map)}</b><em>Bo${(R.maps||[]).length>3?3:1} 未启用</em></div>
        </div>`).join('')}</div>
    </div>` : '';

  const links = [];
  const L = R.links || {};
  if(L.hltv_match) links.push([L.hltv_match, 'HLTV 全场统计']);
  (L.hltv_maps||[]).forEach(g => links.push([g.url, '第 '+(g.game||'?')+' 图 HLTV 数据']));
  (L.vods||[]).forEach(v => links.push([v.url, '第 '+(v.game||'?')+' 图录像']));
  const linkHtml = links.length
    ? `<div class="sec"><div class="sec-h"><b>相关链接</b><i></i><em>跳转外部站点</em></div>
      <div class="links">${links.map(([u,t]) =>
        `<a class="lk" href="${esc(u)}" target="_blank" rel="noopener">${esc(t)} ↗</a>`).join('')}</div></div>`
    : '';

  const nikoBlock = R.niko
    ? `<div class="sec">
        <div class="sec-h"><b>${esc(d.player.nick)} 本场数据</b><i></i><em>HLTV</em></div>
        <div class="grid">
          <div class="st"><span>系列赛评分</span><b>${avg !== null ? avg.toFixed(2) : '—'}</b></div>
          ${(R.niko.kd ? `<div class="st"><span>击杀 / 死亡</span><b>${esc(R.niko.kd)}</b></div>` : '')}
          ${(R.niko.adr ? `<div class="st"><span>场均伤害 ADR</span><b>${esc(R.niko.adr)}</b></div>` : '')}
        </div>
        ${(R.niko.note ? `<div class="kv" style="margin-top:10px"><div class="kv-row"><span>备注</span><b>${esc(R.niko.note)}</b></div></div>` : '')}
        ${!avg && !R.niko.kd ? '<div class="empty">本场评分待回补（HLTV 数据源暂时受限，数据管线会在可访问时自动补齐）</div>' : ''}
      </div>`
    : (R.isNiko
        ? `<div class="sec"><div class="sec-h"><b>${esc(d.player.nick)} 本场数据</b><i></i><em>HLTV</em></div>
            <div class="empty">NiKo 逐图评分来自 HLTV，数据管线将在可访问时自动补齐；下方为双方逐图对局情况。</div></div>`
        : '');

  const backHref = R.source==='event' ? 'event.html' : 'index.html';
  app.innerHTML = `
  <div class="back"><a class="lk" href="${backHref}">‹ 返回</a></div>
  <div class="hero">
    <div class="hero-top"><span class="tag">比赛详情</span></div>
    <div class="hero-body">
      <div class="vs">
        <div class="team">${esc(R.a.name)}</div>
        <div class="vs-mid">${esc(R.scoreText)}</div>
        <div class="team">${esc(R.b.name)}</div>
      </div>
      <div class="hero-sub">${esc(R.dateText)}</div>
      <div class="hero-note">${esc(outcome)} · ${boText(R.bo)} · ${esc(R.event)}</div>
    </div>
  </div>

  <div class="sec">
    <div class="sec-h"><b>逐图详情</b><i></i><em>${played.length} 张地图</em></div>
    ${mapHtml}
  </div>

  ${vetoHtml}

  ${nikoBlock}

  ${linkHtml}

  <div class="syncbar"><span id="liveStatus">○ 正在获取最新数据…</span></div>
  <div class="foot">
    地图回合按「进攻方 / 防守方」拆分；加时回合不计入该项统计。<br>
    地图背景为该地图的游戏内实景（Liquipedia，CC BY-SA 3.0）。最近更新：__UPDATED__
  </div>`;
  lazyMapBg();
}

/* 比赛详情页的对阵、比分、逐图回合全部来自 event.json。
   页面内置的只是一份构建时快照 —— 必须像首页那样主动去拉实时 event.json，
   否则每 5 分钟提交进仓库的最新比分永远到不了这里：比赛打完了，
   详情页还停在构建那一刻的 0:0（2026-10-05 修复）。
   （旧实现只调 sync()，那拉的是 data.json＝NiKo 自己比赛的历史库，
     根本不含赛事分支图里的对阵，于是详情页永远是死的。） */
let _evFp = eventFingerprint(evData());
async function boot(){
  render();                                   // 先用内置快照秒开，不阻塞首屏
  const tick = async () => {
    const r = await pullEvent();              // 实时 event.json
    if(r){
      const fp = eventFingerprint(r.data);
      if(fp !== _evFp){ _evFp = fp; EV_FRESH = r.data; render(); }
    }
    const tag = await sync(null);             // data.json：NiKo 视角比赛的逐图评分等
    // render() 之后 #liveStatus 已是新元素，必须重新取，否则往已卸载的节点上写字
    const el = document.getElementById('liveStatus');
    if(el) el.textContent = r
      ? '● 已同步最新赛事数据（' + r.tag + '）· ' + new Date().toLocaleTimeString('zh-CN')
      : (tag ? '● 已同步最新数据（' + tag + '）' : '○ 使用内置数据（远端暂无更新）');
  };
  await tick();
  setInterval(tick, 60000);
}
"""

TEAM_JS = CORE_JS + r"""
function render(){
  const d = dataOf(), P = d.player, SQ = d.squad || [];
  const app = document.getElementById('app');
  const cards = SQ.map(p => `
    <a class="tc" href="player.html?id=${encodeURIComponent(p.id)}">
      <div class="ph">${avatar(p.photo, p.id, 'lg')}</div>
      <div class="pid">${esc(p.id)}</div>
      <div class="pfull">${esc(p.name || '')}</div>
      <div class="prole">${esc(p.role)}</div>
      <div class="pdesc">${esc(p.note || '')}</div>
    </a>`).join('') || '<div class="empty">暂无阵容数据</div>';

  app.innerHTML = `
  <div class="back"><a class="lk" href="index.html">‹ 返回首页</a></div>
  <div class="hero">
    <div class="hero-top"><span class="tag">所属战队</span></div>
    <div class="hero-body">
      <div class="vs"><div class="team">${esc(P.team)}</div></div>
      <div class="hero-sub">${esc(P.country)} · 世界排名 #${esc(P.team_rank)} · ${esc(P.team_points)} 分</div>
    </div>
  </div>

  <div class="sec">
    <div class="sec-h"><b>成员</b><i></i><em>${SQ.length} 人</em></div>
    <div class="team-grid">${cards}</div>
  </div>

  <div class="sec">
    <div class="sec-h"><b>战队信息</b><i></i><em>Liquipedia</em></div>
    <div class="kv">
      <div class="kv-row"><span>战队名</span><b>${esc(P.team)}</b></div>
      <div class="kv-row"><span>当前世界排名</span><b>第 ${esc(P.team_rank)} 位（${esc(P.team_points)} 分）</b></div>
      <div class="kv-row"><span>核心选手</span><b>${esc(P.nick)}</b></div>
      <div class="kv-row"><span>加入时间</span><b>${esc(P.joined || '—')}</b></div>
      <div class="kv-row"><span>阵容</span><b>${SQ.map(p => esc(p.id)).join(' · ')}</b></div>
      <div class="kv-row"><span>资料页</span><b><a href="https://liquipedia.net/counterstrike/Team_Falcons"
        target="_blank" rel="noopener" style="color:var(--amber)">Liquipedia ↗</a></b></div>
    </div>
  </div>

  <div class="syncbar"><span id="liveStatus">○ 正在获取最新数据…</span></div>
  <div class="foot">阵容与选手资料抓取自 Liquipedia（CC BY-SA 3.0）。最近更新：__UPDATED__</div>`;
}

async function boot(){
  render();
  const st = document.getElementById('liveStatus');
  sync(st);
  setInterval(() => sync(st), 60000);   // 阵容页也每 60 秒同步远端数据（与首页/赛事页一致），避免打开后一直停在旧快照
}
"""

PLAYER_JS = CORE_JS + r"""

/* ---------- 近期比赛（链到 match.html 详情页） ---------- */
function recentMatchesSec(){
  const ms = (dataOf().recent_matches || []).slice()
    .sort((a,b)=> String(b.date).localeCompare(String(a.date))).slice(0, 30);
  if(!ms.length) return '';
  const rows = ms.map(m => {
    const rs = (m.niko && m.niko.ratings) || [];
    const avg = rs.length ? rs.reduce((a,b)=>a+b,0)/rs.length : null;
    return `<a class="row ${m.result}" href="match.html?id=${encodeURIComponent(m.id)}">
      <div class="res ${m.result}">${m.result==='W'?'胜':'负'}</div>
      <div class="sc">${esc(m.score)}</div>
      <div class="info"><div class="o">${esc(m.opponent)}</div>
        <div class="e">${esc(m.event)} · ${boText(m.bo)}</div></div>
      <div class="rt">${avg!==null
        ? `<b>${avg.toFixed(2)}</b><small>评分</small>`
        : `<small style="padding-top:6px" title="评分数据源（HLTV）受限，待自动回补">—</small>`}</div>
      <div class="chev">›</div>
    </a>`;
  }).join('');
  return `<div class="sec"><div class="sec-h"><b>近期比赛</b><i></i>
    <em>点击查看逐图详情与数据</em></div>
    <div class="rows">${rows}</div></div>`;
}

/* ---------- 资料卡（分组 + 强调样式） ---------- */
function pinfoCard(title, tag, cells, full){
  const mk = c => `<div class="pi"><div class="pi-k">${esc(c.k)}</div>
    <div class="pi-v ${c.cls || ''}">${c.html != null ? c.html : esc(c.v)}</div></div>`;
  const ok = c => c && (c.html != null || (c.v !== '' && c.v != null));
  const a = (cells || []).filter(ok).map(mk).join('');
  const b = (full || []).filter(ok).map(mk).join('');
  if(!a && !b) return '';
  return `<div class="pcard">
    <div class="pcard-h"><b>${esc(title)}</b>${tag ? `<em>${esc(tag)}</em>` : ''}</div>
    ${a ? `<div class="pgrid">${a}</div>` : ''}
    ${b ? `<div class="pgrid one" style="margin-top:12px">${b}</div>` : ''}
  </div>`;
}

/* ---------- 页面 ---------- */
function render(){
  const d = dataOf(), id = params.get('id') || d.player.nick;
  const app = document.getElementById('app');
  const p = (d.squad || []).find(x => x.id === id);
  if(!p){
    app.innerHTML = `<div class="back"><a class="lk" href="index.html">‹ 返回</a></div>
      <div class="empty" style="margin-top:30px">没有这位选手的资料<br><br>
      <a class="lk" href="team.html">查看阵容</a></div>`;
    return;
  }
  const isNiko = p.id === d.player.nick;
  const P = d.player, c = P.career || {}, g = P.gear || {}, x = P.crosshair || {};
  const PLIST = photosData();
  const photoSrc = (isNiko && PLIST.length) ? PLIST[0].src : p.photo;

  /* 顶部大图 */
  const hero = `<div class="phero">
    <img class="phero-img" src="${esc(photoSrc)}" alt="${esc(p.id)}">
    <div class="phero-scrim"></div>
    <span class="phero-badge"><i class="dot"></i>${esc(p.status || '现役')} · ${esc(p.team || '')}</span>
    ${(isNiko && PLIST.length) ? `<span class="phero-gal" id="heroGal">照片墙 ${PLIST.length} 张 ›</span>` : ''}
    <div class="phero-id">
      <div class="phero-name">${esc(p.id)}</div>
      <div class="phero-full">${esc(p.name || '')}${p.native_name ? ' · ' + esc(p.native_name) : ''}</div>
      <div class="phero-meta">
        <b>${esc(p.nationality || '')}</b><i class="sep"></i><span>${esc(p.role || '')}</span>
        ${p.age ? `<i class="sep"></i><span>${p.age} 岁</span>` : ''}
        ${isNiko ? `<i class="sep"></i><span>世界排名 <b>#${esc(P.team_rank)}</b></span>` : ''}
      </div>
    </div>
  </div>`;

  /* 关键数据 chips */
  const chips = isNiko ? `<div class="pchips">
    <div class="chip hl"><b>${P.rating_3m.toFixed(2)}</b><span>近三月评分</span></div>
    <div class="chip"><b>#${esc(P.team_rank)}</b><span>世界排名</span></div>
    <div class="chip"><b>${(c.kills || 0).toLocaleString('en-US')}</b><span>生涯击杀</span></div>
    <div class="chip"><b>${(c.kd || 0).toFixed(2)}</b><span>生涯 K/D</span></div>
    <div class="chip"><b>${esc(c.mvp)}</b><span>大赛 MVP</span></div>
    <div class="chip"><b>${esc(c.top20)}</b><span>TOP20</span></div>
    <div class="chip"><b>${esc(P.winnings)}</b><span>生涯奖金</span></div>
  </div>` : '';

  /* 个人简介 */
  const bioTxt = isNiko ? NIKO_BIO : (p.note ? esc(p.note) : '');
  const bio = bioTxt ? `<div class="pbio">
    <div class="pbio-h">${isNiko ? '个人简介' : '选手简介'}</div>
    <p>${bioTxt}</p>
  </div>` : '';

  /* 个人资料：基本信息 / 战队信息 / 荣誉与生涯 */
  const gBase = pinfoCard('基本信息', 'Liquipedia', [
    {k:'本名', v:p.name},
    {k:'母语名', v:p.native_name},
    {k:'国籍', v:p.nationality},
    {k:'出生', v:p.born},
    {k:'年龄', v:p.age ? p.age + ' 岁' : ''},
    {k:'选手状态', v:p.status, cls:'grad'},
    {k:'职业年限', v:p.years_active},
    {k:'队内角色', v:p.role}
  ], [
    {k:'曾用 ID', v:p.alt_ids, cls:'mono'}
  ]);

  const gTeam = pinfoCard('战队信息', isNiko ? P.team : p.team, [
    {k:'所属战队', v:p.team, cls:'grad'},
    {k:'加入日期', v:isNiko ? P.joined : ''},
    {k:'世界排名', v:isNiko ? '#' + P.team_rank : ''},
    {k:'队伍积分', v:isNiko ? P.team_points : ''},
    {k:'教练', v:isNiko ? P.coach : ''}
  ], [
    {k:'队友', v:(isNiko && (P.teammates || []).length) ? P.teammates.join(' · ') : ''}
  ]);

  const honors = [];
  if(isNiko){
    if((P.major || {}).title) honors.push({k:'MAJOR 冠军', html:
      `${esc(P.major.title)} <span style="color:var(--dim);font-weight:400">${esc(P.major.result || '')}</span>`});
    honors.push({k:'生涯奖金', v:P.winnings, cls:'grad'});
    honors.push({k:'HLTV TOP20', v:(c.top20 || 0) + ' 次'});
    honors.push({k:'大赛 MVP', v:(c.mvp || 0) + ' 次'});
    honors.push({k:'出场地图', v:(c.maps || 0).toLocaleString('en-US')});
    honors.push({k:'生涯 ADR', v:c.adr});
    honors.push({k:'爆头率', v:(c.hs || 0) + '%'});
    honors.push({k:'每回合击杀', v:c.kpr});
  }
  const gHonor = isNiko ? pinfoCard('荣誉与生涯', 'HLTV', honors,
    (P.major && P.major.note) ? [{k:'MAJOR 备注', v:P.major.note}] : []) : '';

  /* 战队经历 */
  const hist = (p.history || []).length ? `<div class="pcard">
    <div class="pcard-h"><b>战队经历</b><em>${p.history.length} 段</em></div>
    <div class="pgrid one">${p.history.slice().reverse().map(h => `
      <div class="pi" style="display:flex;align-items:baseline;gap:10px">
        <span style="font-size:14.5px;font-weight:700;color:var(--ink)">${esc(h.team)}</span>
        <span class="pi-k" style="margin-left:auto;white-space:nowrap">${esc(h.from)} → ${esc(h.to)}</span>
      </div>`).join('')}</div></div>` : '';

  /* 外设与设置 */
  const gearCard = isNiko ? pinfoCard('外设与设置', 'Liquipedia', [
    {k:'鼠标', v:g.mouse}, {k:'鼠标垫', v:g.mousepad},
    {k:'游戏内灵敏度', v:g.sens}, {k:'DPI', v:g.dpi}, {k:'eDPI', v:g.edpi},
    {k:'轮询率', v:g.polling}, {k:'显示器', v:g.monitor}, {k:'刷新率', v:g.refresh},
    {k:'分辨率', v:g.resolution}, {k:'键盘', v:g.keyboard}, {k:'耳机', v:g.headset}
  ]) : '';

  /* 准星 */
  const xCard = isNiko ? `<div class="sec">
    <div class="sec-h"><b>准星</b><i></i><em>${P.crosshair_sharecode ? '含分享码' : ''}</em></div>
    <div class="pcard">
      <div class="xh" id="xhBox"></div>
      <div class="pgrid" style="margin-top:14px">
        <div class="pi"><div class="pi-k">参数</div><div class="pi-v">样式 ${esc(x.style || '—')} · 长度 ${esc(x.size || '—')} · 粗细 ${esc(x.thickness || '—')} · 间隙 ${esc(x.gap || '—')}</div></div>
        <div class="pi"><div class="pi-k">颜色</div><div class="pi-v"><i style="display:inline-block;width:10px;height:10px;border-radius:2px;background:#00FF91;vertical-align:middle;margin-right:6px"></i>自定义绿 #00FF91${(x.outline === 'No' || x.outline === '否') ? ' · 无描边' : ''}${(x.dot === 'No' || x.dot === '否') ? ' · 无中心点' : ''}</div></div>
        <div class="pi"><div class="pi-k">分享码</div><div class="pi-v mono">${esc(P.crosshair_sharecode || '—')}</div></div>
      </div>
    </div>
  </div>` : '';

  app.innerHTML = `
  <div class="back"><a class="lk" href="team.html">‹ 返回队伍</a></div>
  ${hero}
  ${chips}
  ${bio}
  ${isNiko ? pwallSec() : ''}
  ${isNiko ? recentMatchesSec() : ''}
  <div class="sec">
    <div class="sec-h"><b>个人资料</b><i></i><em>Liquipedia</em></div>
    <div class="pinfo">${gBase}${gTeam}${gHonor}${hist}</div>
  </div>
  ${gearCard ? `<div class="sec"><div class="sec-h"><b>外设与设置</b><i></i><em>Liquipedia</em></div>${gearCard}</div>` : ''}
  ${xCard}
  <div class="links">
    <a class="lk" href="${esc(p.url || '#')}" target="_blank" rel="noopener">Liquipedia 资料页 ↗</a>
    <a class="lk" href="index.html">返回首页</a>
  </div>
  <div class="syncbar"><span id="liveStatus">○ 正在获取最新数据…</span></div>
  <div class="foot">选手资料与官方照片抓取自 Liquipedia（CC BY-SA 3.0）。最近更新：__UPDATED__</div>
  ${isNiko ? plbHtml() : ''}`;

  if(isNiko){ drawCrosshair(x); bindPhotos(); }
}

async function boot(){
  await Promise.all([pullPhotos(), pullNewest()]);
  render();
  const st = document.getElementById('liveStatus');
  sync(st);
  setInterval(() => sync(st), 60000);   // 选手页也每 60 秒同步远端数据（与首页/赛事页一致），避免打开后一直停在旧快照
}
"""

EVENT_JS = CORE_JS + r"""
let CUR = null;
let CUR_URL_DONE = false;   // URL ?id= 深链只在首次 render 采纳；
                            // 之后由 tab 点击接管。params 是加载时的快照，
                            // 若每次 render 都读它，点击切换会被旧 URL 强行改回去

function teamChip(name, TM){
  if(!name) return '<em>待定</em>';
  const logo = TM[name];
  const img = logo ? `<img src="${esc(logo)}" alt="" loading="lazy">` : '';
  return img + '<em>' + esc(name) + '</em>';
}

function evTabs(EVS){
  return EVS.map(e => {
    const on = e.id === CUR ? ' on' : '';
    return `<button class="ev-tab${on}" data-ev="${esc(e.id)}">
      <b>${esc(e.short || e.name)}</b>
      <small>${e.tag === 'next' ? '下一站' : '已结束'} · ${esc(e.date_text || '')}</small>
    </button>`;
  }).join('');
}

function evCard(e){
  const meta = [
    ['赛程日期', e.date_text || '—'],
    ['赛事等级', tierText(e.tier) || '—'],
    ['奖池', e.prize || '—'],
    ['参赛队伍', (e.teams || []).length ? (e.teams.length + ' 支') : '待公布']
  ].map(([k, v]) => `<div class="ev-mi"><span>${k}</span><b>${esc(v)}</b></div>`).join('');
  const cd = (liveStatus(e.start, e.end) === 'upcoming' && e.start) ? `<div class="ev-count" id="evCount">
      <div class="ev-cd"><b id="cdD">–</b><span>天</span></div>
      <div class="ev-cd"><b id="cdH">–</b><span>小时</span></div>
      <div class="ev-cd"><b id="cdM">–</b><span>分钟</span></div>
      <div class="ev-cd"><b id="cdS">–</b><span>秒</span></div>
    </div>` : '';
  return `<div class="ev-card">
    <div class="ev-top">
      <div class="ev-name">${esc(e.name)}</div>
      <div class="ev-badge">
        <span class="ev-b gold">${esc(tierText(e.tier) || 'S 级')}</span>
        <span class="ev-b ${statusCls(liveStatus(e.start, e.end))}">${statusCn(liveStatus(e.start, e.end))}</span>
      </div>
    </div>
    <div class="ev-meta">${meta}</div>
    ${e.format ? `<div class="ev-fmt">${esc(e.format)}</div>` : ''}
    ${cd}
    <a class="ev-cta" href="${esc(e.source)}" target="_blank" rel="noopener">Liquipedia 赛事页 ↗</a>
  </div>`;
}

function teamsSec(e){
  const ts = e.teams || [];
  if(!ts.length) return '';
  const list = ts.map(t => {
    const hl = /falcons/i.test(t.name) ? ' hl' : '';
    const img = t.logo ? `<img src="${esc(t.logo)}" alt="" loading="lazy">`
                       : `<span class="mono">${ini(t.name)}</span>`;
    return `<div class="tm${hl}">${img}<em>${esc(t.name)}</em></div>`;
  }).join('');
  return `<div class="sec">
    <div class="sec-h"><b>参赛队伍</b><i></i><em>${ts.length} 支</em></div>
    <div class="teams">${list}</div>
  </div>`;
}

/* 分组/瑞士轮积分 → 排行榜卡片（队标 + 队名 + 战绩）。
   数据映射（Liquipedia 瑞士轮表 "Overview"）：
     nums[0] = 战绩 (W-L，如 3-1)
     nums[1] = 回合 (W-L，如 118-100)
     nums[2..] = 各轮系列赛比分（依次为 Round 1、2、3…，BO 比分如 2:0）
   净胜（RD）不取原文——Liquipedia 的 RD 列写作 "+39"/"-5"，
   parse_event 的数值过滤只认纯数字，该列会被丢掉；这里用 nums[1] 现算，
   既避免列错位，也保证与回合数一致。 */
function wlPair(s){
  const m = String(s || '').match(/^(\d+)\s*[-:]\s*(\d+)$/);
  return m ? [+m[1], +m[2]] : null;
}

/* 晋级区名次线（ESL 职业联赛瑞士轮：前 8 名进淘汰赛） */
const GRP_CUT = 8;

function groupsSec(e){
  const gs = e.groups || [];
  if(!gs.length) return '';
  return gs.map(g => {
    const rs = g.rows || [];
    // 轮次槽位数固定取自表头（Round 1..n），每行都渲染同样多的色块——不足的补虚线空槽。
    // 这样所有行宽度一致，窄屏上要么全部换行、要么全部单行，行高整齐。
    const roundN = Math.max(1, (g.cols || []).filter(c => /^Round\s*\d+$/i.test(c)).length || 5);
    const rows = rs.map((r, i) => {
      const n = r.nums || [];
      const rec = wlPair(n[0]);                    // 战绩
      const rd  = wlPair(n[1]);                    // 回合
      const form = n.slice(2);                     // 各轮系列赛比分
      const rank = i + 1;
      const hl = /falcons/i.test(r.team) ? ' hl' : '';
      // 分区色：ESL 职业联赛瑞士轮「前 8 名晋级淘汰赛」（Liquipedia Format 段原文
      // "Top 8 teams proceed to Playoffs"），故按名次分成晋级区/淘汰区两档。
      // 类名带 z- 前缀，避免与项目已有的 .up{display:grid} 撞车。
      const zone = rank <= GRP_CUT ? ' z-up' : ' z-down';
      const logo = teamLogo(e, r.team);
      const img = logo ? `<img src="${esc(logo)}" alt="" loading="lazy">`
                       : `<span class="ph">${esc(ini(abbrTeam(r.team)))}</span>`;
      const wlCls = rec ? (rec[0] > rec[1] ? ' good' : (rec[0] < rec[1] ? ' bad' : '')) : '';
      const diff = rd ? rd[0] - rd[1] : null;
      const meta = [
        n[1] ? `<span class="lb-m">回合 <b>${esc(n[1])}</b></span>` : '',
        diff === null ? '' : `<span class="lb-m">净胜 <b class="${diff > 0 ? 'g' : (diff < 0 ? 'r' : '')}">`
          + `${diff > 0 ? '+' : ''}${diff}</b></span>`
      ].filter(Boolean).join('');
      const cells = [];
      for(let k = 0; k < roundN; k++){
        const s = form[k];
        if(!s){ cells.push(`<i class="e" title="第 ${k + 1} 轮 未开赛">–</i>`); continue; }
        const w = wlPair(s);
        const win = w ? w[0] > w[1] : false;
        cells.push(`<i class="${win ? 'w' : 'l'}" title="第 ${k + 1} 轮 ${esc(s)}">${esc(s)}</i>`);
      }
      const chips = `<span class="lb-form">${cells.join('')}</span>`;
      const sub = (meta || chips) ? `<div class="lb-sub">${meta}${chips}</div>` : '';
      return `<div class="lb-r${zone}${hl}">
        <div class="lb-main">
          <span class="lb-rk${rank <= 3 ? ' t' + rank : ''}">${rank}</span>
          <span class="lb-tm">${img}<b class="${hl ? 'hl' : ''}">${esc(r.team)}</b></span>
          ${rec ? `<span class="lb-wl${wlCls}">${esc(n[0])}</span>` : ''}
        </div>${sub}
      </div>`;
    }).join('');
    return `<div class="sec">
      <div class="sec-h"><b>分组积分</b><i></i><em>${esc(g.title === 'Overview' ? '总览' : g.title)} · ${rs.length} 支</em></div>
      <div class="lb">${rows}</div>
      <div class="lb-foot"><b class="w"></b>晋级区（前 ${GRP_CUT} 名进淘汰赛）
        <b class="l"></b>淘汰区 · 色块＝各轮系列赛比分（第 1 轮 → 第 ${roundN} 轮）</div>
    </div>`;
  }).join('');
}

function brkMatch(m, TM){
  // 同时进行中：开赛时间已过但未超时，即便已经有比分也要算 LIVE，
  // 否则正在打的比赛会被当成已结束（只有胜负样式、没有 LIVE 标记）
  // ts 走 matchTs()：小组赛(matchlist)那场 m.ts 常为 null，靠 id 兜底取到真实开赛时间，
  // 否则未开赛场次既不算 LIVE 也不显示时间（2026-10-05 需求：分支图显示「几号几点」）。
  const ts = matchTs(m);
  const played = m.a.score !== null || m.b.score !== null;
  const live = ts ? isLive(ts) : false;
  const row = (t, isA) => {
    let cls = 'brk-o';
    if(played) cls += t.win ? ' w' : ' l';
    // 紧凑条：队标 + 缩写（全名太长会把列撑宽，破坏「一屏放下」）
    const logo = TM[t.name];
    const img = logo ? `<img src="${esc(logo)}" alt="" loading="lazy">` : '';
    return `<div class="${cls}">${img}<em>${esc(abbrTeam(t.name))}</em>`
      + '<s>' + (t.score === null ? '–' : t.score) + '</s></div>';
  };
  const tag = live ? '<i>LIVE</i>'
    : (played ? '' : (ts ? '<i style="color:var(--dim);font-weight:600">'
        + bjShort(ts) + '</i>' : ''));
  return `<div class="brk-m${live ? ' live' : ''}">
    ${row(m.a, true)}${row(m.b, false)}
    <div class="brk-mt">${esc(m.bo || '')}${tag}</div>
    <span class="brk-go">›</span>
  </div>`;
}

function bracketsSec(e){
  const bs = (e.brackets || []).filter(b => b.count);
  if(!bs.length) return `<div class="sec">
    <div class="sec-h"><b>分支图</b><i></i><em>对阵树</em></div>
    <div class="empty">${(liveStatus(e.start, e.end) === 'upcoming')
      ? '淘汰赛阶段开始后，分支图将自动出现并每 60 秒同步'
      : '分组与对阵尚未公布'}<br>数据来自 Liquipedia（CC BY-SA 3.0）</div>
    </div>`;
  const sorted = bs.slice().sort((a, b) => (isPlayoff(b.title) ? 1 : 0) - (isPlayoff(a.title) ? 1 : 0));
  return sorted.map(b => {
    const cols = b.rounds.map(rd => `<div class="brk-r">
        <div class="brk-rt">${esc(zhRound(rd.name))}</div>
        <div class="brk-rb">${rd.matches.map(m => `<a class="brk-lk" href="match.html?id=${esc(m.id||'')}">${brkMatch(m, e._TM)}</a>`).join('')}</div>
      </div>`).join('');
    return `<div class="sec">
      <div class="sec-h"><b>${esc(zhRound(b.title))}</b><i></i><em>${b.count} 场对阵</em></div>
      <div class="brk-wrap"><div class="brk">${cols}</div></div>
    </div>`;
  }).join('');
}

/* 分支图「一屏放下」：列宽固定 104px，列数多时整块等比缩小而不是横向右滑
   （2026-10-05：原来 min-width:190px 固定列 + 右滑，手机上要划好几屏才看得完）。
   做法：量出 .brk 自然宽度，和容器可用宽度比，scale = min(1, 可用/自然)，
   再把缩放后的高度补回去（transform 不改变布局高度，不补会留白）。 */
/* 分支图自适应：把实测列宽写进 --cw，卡内所有尺寸（字号/队标/间距/比分）都用
   calc(var(--cw)*系数) 派生 → 列宽随窗口任意变化时内容同比缩放。
   不用 transform:scale + overflow-x:auto —— 那套在列多时会触到缩放下限、
   仍能拖动滑来滑去（2026-10-08 用户反馈）。现在列 flex:1 均分容器、
   容器无 overflow，任何窗口宽度都不产生滚动条。 */
function fitBrackets(){
  document.querySelectorAll('.brk-wrap').forEach(w => {
    const col = w.querySelector('.brk-r');
    if(!col) return;
    // getBoundingClientRect 拿到的是已应用 flex 均分后的真实列宽（含 gap 影响）
    const cw = col.getBoundingClientRect().width;
    if(cw > 0) w.style.setProperty('--cw', cw + 'px');
  });
}

function schRow(m){
  // 同时进行中：有时间窗就算 LIVE，不等到出比分才判定（见 brkMatch 同款逻辑）
  const played = m.sa !== null && m.sb !== null;
  const live = m.ts ? isLive(m.ts) : false;
  const wA = played && m.sa > m.sb;
  const nA = wA ? '<b>' + esc(m.a) + '</b>' : esc(m.a);
  const nB = (played && !wA) ? '<b>' + esc(m.b) + '</b>' : esc(m.b);
  return `<div class="sch${live ? ' live' : ''}">
    <div class="t">${bjHM(m.ts)}</div>
    <div class="n">${nA} <span style="color:var(--dim)">vs</span> ${nB}</div>
    ${live ? '<span class="tag-live">LIVE</span>' : ''}
    <div class="s">${played ? m.sa + ':' + m.sb : '—'}</div>
    <div class="q">${esc(m.bo || '')}</div>
    <span class="sch-go">›</span>
  </div>`;
}
function scheduleSec(e){
  const s = (e.schedule || []).slice().sort((a, b) => a.ts - b.ts);
  if(!s.length) return `<div class="sec">
    <div class="sec-h"><b>赛程与实时比分</b><i></i><em>按北京时间</em></div>
    <div class="empty">赛程尚未公布<br>开赛后这里会显示每场对阵与实时比分</div>
    </div>`;
  const days = [];
  s.forEach(m => {
    const k = bjDayLabel(m.ts);
    let last = days[days.length - 1];
    if(!last || last.k !== k){ last = {k, rows: []}; days.push(last); }
    last.rows.push(m);
  });
  const body = days.map(d => `<div class="sch-d">${esc(d.k)}</div>
    ${d.rows.map(m => `<a class="sch-lk" href="match.html?id=${esc(m.id||'')}">${schRow(m)}</a>`).join('')}`).join('');
  return `<div class="sec">
    <div class="sec-h"><b>赛程与实时比分</b><i></i><em>北京时间 · ${s.length} 场</em></div>
    ${body}
  </div>`;
}

function render(){
  const data = evData();
  const EVS = data.events || [];
  const app = document.getElementById('app');
  if(!EVS.length){
    app.innerHTML = `<div class="back"><a class="lk" href="index.html">‹ 返回首页</a></div>
      <div class="empty" style="margin-top:30px">暂无赛事数据</div>`;
    return;
  }
  if(!CUR_URL_DONE){
    const want = params.get('id');
    if(want && EVS.some(x => x.id === want)) CUR = want;
    CUR_URL_DONE = true;
  }
  if(!CUR || !EVS.some(x => x.id === CUR))
    CUR = (data.featured && data.featured.id) || EVS[0].id;
  const e = EVS.find(x => x.id === CUR);
  // 队名 -> 队标
  e._TM = {};
  (e.teams || []).forEach(t => { e._TM[t.name] = t.logo; });

  app.innerHTML = `
  <div class="back"><a class="lk" href="index.html">‹ 返回首页</a></div>
  <div class="sec">
    <div class="sec-h"><b>赛事中心</b><i></i><em>分组 · 分支图 · 实时比分</em></div>
    <div class="ev-tabs">${evTabs(EVS)}</div>
    ${evCard(e)}
  </div>
  ${teamsSec(e)}
  ${groupsSec(e)}
  ${bracketsSec(e)}
  ${scheduleSec(e)}
  <div class="syncbar"><span id="liveStatus">○ 正在获取最新赛事数据…</span></div>
  <div class="foot">
    赛事分组、分支图与比分抓取自 Liquipedia（CC BY-SA 3.0），每 60 秒自动同步一次。<br>
    最近更新：__UPDATED__
  </div>`;

  app.querySelectorAll('.ev-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      CUR = btn.getAttribute('data-ev');
      render();
      history.replaceState(null, '', location.pathname + '?id=' + encodeURIComponent(CUR));
      window.scrollTo({top: 0, behavior: 'smooth'});
    });
  });
  if(liveStatus(e.start, e.end) === 'upcoming' && e.start) startCountdown(e.start);
  // 分支图自适应：等布局算出真实列宽后再写 --cw（requestAnimationFrame 保证已 reflow）
  requestAnimationFrame(fitBrackets);
}
// 窗口尺寸/横竖屏变化时重算列宽（地址栏收起、旋转屏在部分浏览器不触发 resize）
function refitBrackets(){
  clearTimeout(window.__brkFitT);
  window.__brkFitT = setTimeout(fitBrackets, 120);
}
window.addEventListener('resize', refitBrackets);
window.addEventListener('orientationchange', refitBrackets);

async function boot(){
  render();                     // 先渲染内置数据，不阻塞
  renderWarnBanner();           // 改版降级横幅（event.json 带 parse_warning 时显示）
  const st = document.getElementById('liveStatus');
  if(st) st.textContent = '● 赛事数据已载入 · 每 60 秒自动同步';
  let _fp = eventFingerprint(evData());
  /* 首屏必须立刻拉一次：旧实现只在 setInterval 里拉，加载后整整 60 秒都停在
     构建时快照上——刚打完的比赛那 60 秒里就是 0:0（2026-10-05 修复）。 */
  const tick = async () => {
    const r = await pullEvent();
    if(!r) return;              // 联网失败，保留内置/上次数据，下次再试
    const fp = eventFingerprint(r.data);
    if(fp !== _fp){ _fp = fp; EV_FRESH = r.data; render(); }  // 内容真变了才重渲染（保留滚动位置）
    renderWarnBanner();         // 联网同步后重新评估降级状态
    if(r.data && r.data.updated){
      document.querySelectorAll('.foot').forEach(el => {
        el.textContent = el.textContent.replace(/最近更新：[\s\S]*$/, '最近更新：' + r.data.updated);
      });
    }
    // render() 之后 #liveStatus 是新元素，必须重新取
    const el = document.getElementById('liveStatus');
    if(el) el.textContent = '● 已同步（' + r.tag + '）· ' + new Date().toLocaleTimeString('zh-CN');
  };
  tick();
  setInterval(tick, 60000);
}
"""

PAGES = [
    ("index.html", "index", "NiKo // 赛事跟踪", INDEX_JS,
     "NiKo（Nikola Kovač）赛事跟踪：Team Falcons 赛程、比分与选手数据"),
    ("event.html", "event", "赛事中心 // NiKo", EVENT_JS,
     "当前赛事与最近赛事：分组、分支图、赛程与实时比分"),
    ("match.html", "match", "比赛详情 // NiKo", MATCH_JS, "NiKo 比赛逐图详情"),
    ("team.html", "team", "Team Falcons // 阵容", TEAM_JS, "Team Falcons 现役阵容与选手资料"),
    ("player.html", "player", "选手资料 // NiKo", PLAYER_JS, "NiKo 与队友的选手资料"),
]


def build_page(fname, pid, title, js, desc):
    updated = DATA["meta"]["updated"]
    body = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#EEF0FB">
<meta name="description" content="{desc}">
<title>{title}</title>
<!-- 图标 = NiKo 本人高清照片（2048px 原图裁切，人脸居中），非像素图 -->
<link rel="icon" type="image/png" sizes="48x48" href="assets/pixel/favicon-48.png?v=3">
<link rel="icon" type="image/png" sizes="32x32" href="assets/pixel/favicon.png?v=3">
<!-- iOS 主屏图标：补齐多档高分辨率尺寸，系统会自动挑最清晰的一张 -->
<link rel="apple-touch-icon" sizes="180x180" href="assets/pixel/apple-touch-icon.png?v=3">
<link rel="apple-touch-icon" sizes="152x152" href="assets/pixel/apple-touch-icon-152.png?v=3">
<meta name="apple-mobile-web-app-title" content="NIKO">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<link rel="manifest" href="manifest.json">
<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
<link rel="dns-prefetch" href="https://raw.githubusercontent.com">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&family=Noto+Serif+SC:wght@600;700;900&family=Rajdhani:wght@500;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style>
{SWIPE_BACK_JS}
</head>
<body data-page="{pid}">
{ARMS_SPRITE}
{ARMS_BG}
<div class="hud"><div class="hud-in">
  <div class="crosshair"><span></span></div>
  <div class="brand"><b>NIKO</b><small>赛事跟踪</small></div>
  <div class="status"><i class="dot" id="dot"></i><span id="statusTxt">待战</span></div>
</div></div>
<div class="wrap" id="app"></div>
<script id="niko-data" type="application/json">__DATA__</script>
<script>
__JS__
render();
boot();
</script>
</body>
</html>"""
    return (body.replace("__JS__", js)
                .replace("__DATA__", json.dumps(DATA, ensure_ascii=False))
                .replace("__UPDATED__", updated)
                .replace("__REPO__", REPO)
                .replace("__MAPBG__", json.dumps(MAP_BG, ensure_ascii=False,
                                                 separators=(",", ":")).replace("</", "<\\/"))
                .replace("__EVENT__", json.dumps(EVENT_DATA, ensure_ascii=False,
                                                 separators=(",", ":")).replace("</", "<\\/"))
                .replace("__PHOTOS__", json.dumps(PHOTOS, ensure_ascii=False,
                                                 separators=(",", ":")).replace("</", "<\\/")))


def main():
    payload = json.dumps(DATA, ensure_ascii=False)
    # 内联数据里不能出现 </script>，否则会截断脚本标签
    payload = payload.replace("</script", "<\\/script")
    # 地图背景 & 赛事数据（同样要防 </script> 截断）
    mapbg_json = json.dumps(MAP_BG, ensure_ascii=False, separators=(",", ":")) \
        .replace("</", "<\\/")
    event_json = json.dumps(EVENT_DATA, ensure_ascii=False, separators=(",", ":")) \
        .replace("</", "<\\/")
    photos_json = json.dumps(PHOTOS, ensure_ascii=False, separators=(",", ":")) \
        .replace("</", "<\\/")
    built = []
    for fname, pid, title, js, desc in PAGES:
        updated = DATA["meta"]["updated"]
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#EEF0FB">
<meta name="description" content="{desc}">
<title>{title}</title>
<!-- 图标 = NiKo 本人高清照片（2048px 原图裁切，人脸居中），非像素图 -->
<link rel="icon" type="image/png" sizes="48x48" href="assets/pixel/favicon-48.png?v=3">
<link rel="icon" type="image/png" sizes="32x32" href="assets/pixel/favicon.png?v=3">
<!-- iOS 主屏图标：补齐多档高分辨率尺寸，系统会自动挑最清晰的一张 -->
<link rel="apple-touch-icon" sizes="180x180" href="assets/pixel/apple-touch-icon.png?v=3">
<link rel="apple-touch-icon" sizes="152x152" href="assets/pixel/apple-touch-icon-152.png?v=3">
<meta name="apple-mobile-web-app-title" content="NIKO">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<link rel="manifest" href="manifest.json">
<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
<link rel="dns-prefetch" href="https://raw.githubusercontent.com">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&family=Noto+Serif+SC:wght@600;700;900&family=Rajdhani:wght@500;600;700&display=swap" rel="stylesheet">
<style>{CSS}</style>
{SWIPE_BACK_JS}
</head>
<body data-page="{pid}">
{ARMS_SPRITE}
{ARMS_BG}
<div class="hud"><div class="hud-in">
  <div class="crosshair"><span></span></div>
  <div class="brand"><b>NIKO</b><small>赛事跟踪</small></div>
  <div class="status"><i class="dot" id="dot"></i><span id="statusTxt">待战</span></div>
</div></div>
<div class="wrap" id="app"></div>
<script id="niko-data" type="application/json">{payload}</script>
<script>
{js.replace("__REPO__", REPO).replace("__UPDATED__", updated)
   .replace("__MAPBG__", mapbg_json).replace("__EVENT__", event_json)
   .replace("__PHOTOS__", photos_json)}
render();
boot();
</script>
</body>
</html>"""
        (ROOT / fname).write_text(html, encoding="utf-8")
        if _gh.exists():
            (_gh / fname).write_text(html, encoding="utf-8")
        built.append((fname, len(html)))
    for name, size in built:
        print(f"{name:14s} {size/1024:6.1f} KB")


if __name__ == "__main__":
    main()
