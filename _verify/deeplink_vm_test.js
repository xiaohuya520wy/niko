/* 复现「点首页 hero 进入赛事中心，却停在旧赛事」：
   首屏内联快照不含新赛事 PGL Singapore → 首次 render 解析 ?id= 失败 →
   CUR 退回旧 featured(IEM 北京) → CUR_URL_DONE=true →  fresh 数据到了也不重试。 */
process.env.TZ = 'Asia/Shanghai';
const fs = require('fs'), vm = require('vm'), path = require('path');
const ROOT = path.join(__dirname, '..');
const which = process.env.EV_PAGE || path.join(ROOT, 'event.html');   // 修复后可指向 _cf_dist
const html = fs.readFileSync(which, 'utf8');
const js = (html.match(/<script>([\s\S]*?)<\/script>/g) || []).pop()
  .replace(/^<script>/, '').replace(/<\/script>$/, '').replace(/render\(\);\s*renderWarnBanner\(\);\s*boot\(\);\s*$/, '');
const staleEV = JSON.parse(fs.readFileSync(path.join(ROOT,'event.json'),'utf8'));     // 构建快照（旧）
const freshEV = JSON.parse(fs.readFileSync(path.join(__dirname,'online_event.json'),'utf8')); // KV 实时（新）
const DATA = JSON.parse(fs.readFileSync(path.join(ROOT,'data.json'),'utf8'));

function makeEl(id){return {id,innerHTML:'',textContent:'',style:{},dataset:{},children:[],
  classList:{add(){},remove(){},toggle(){},contains(){return false}},
  addEventListener(){},removeEventListener(){},querySelectorAll(){return []},querySelector(){return null},
  getAttribute(){return null},setAttribute(){},appendChild(){},removeChild(){},scrollTo(){},click(){},
  getBoundingClientRect(){return {width:0,height:0}}}}
function run(wantId, withFresh){
  const els={'niko-data':makeEl('niko-data')};
  els['niko-data'].textContent=JSON.stringify(DATA);
  const document={getElementById(id){return els[id]||(els[id]=makeEl(id))},querySelectorAll(){return []},
    querySelector(){return null},createElement(){return makeEl('x')},body:makeEl('body'),
    documentElement:makeEl('html'),addEventListener(){}};
  const ctx=vm.createContext({document,console,URLSearchParams,Date,Math,JSON,Intl,Promise,Map,Set,
    String,Number,Array,Object,Boolean,RegExp,Error,TypeError,parseInt,parseFloat,isNaN,
    encodeURIComponent,decodeURIComponent,
    location:{search:'?id='+encodeURIComponent(wantId),pathname:'/event.html',href:'https://x/event.html'},
    history:{replaceState(){}},navigator:{userAgent:'node'},window:{scrollTo(){},addEventListener(){}},
    matchMedia:()=>({matches:false,addListener(){}}),setTimeout:()=>0,clearTimeout(){},setInterval:()=>0,
    requestAnimationFrame:()=>0,fetch:()=>Promise.reject(new Error('offline'))});
  vm.runInContext(js,ctx);
  vm.runInContext('render();',ctx);                       // ① 首屏：内联旧快照
  const first=vm.runInContext('CUR',ctx);
  if(withFresh){
    vm.runInContext('EV_FRESH='+JSON.stringify(freshEV)+'; render();',ctx);  // ② KV 新数据到达
  }
  const cur=vm.runInContext('CUR',ctx);
  const html=els.app.innerHTML;
  const tabOn=(html.match(/class="ev-tab on"[^>]*data-ev="([^"]+)"/)||[])[1]
            ||(html.match(/data-ev="([^"]+)"[^>]*class="ev-tab on"/)||[])[1];
  return {first,cur,tabOn,hasPGL:/pgl-2026-singapore/.test(html),title:(html.match(/<h1[^>]*>([^<]+)/)||[])[1]};
}
const WANT='pgl-2026-singapore';
console.log('=== 场景：首页 hero 链接 ?id='+WANT+' ===');
const r1=run(WANT,false), r2=run(WANT,true);
console.log('首屏(旧快照) CUR=',r1.first);
console.log('KV刷新后    CUR=',r2.cur,'| tab选中=',r2.tabOn,'| 含PGL=',r2.hasPGL);
let fail=0;
if(r2.cur!==WANT){console.log('✗ FAIL: KV 刷新后仍停在',r2.cur,'（应为',WANT+'）');fail++;}
else console.log('✓ PASS: KV 刷新后切到最新赛事');
process.exit(fail?1:0);
