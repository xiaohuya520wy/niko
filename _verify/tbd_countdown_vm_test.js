/* 对手未定时：hero 不显示秒级倒计时，改显示赛事日期 / 待定。
   真实对阵（有对手）时倒计时必须照常工作。 */
process.env.TZ='Asia/Shanghai';
const fs=require('fs'),vm=require('vm'),path=require('path');
const ROOT=path.join(__dirname,'..');
const html=fs.readFileSync(path.join(ROOT,'index.html'),'utf8');
const js=(html.match(/<script>([\s\S]*?)<\/script>/g)||[]).pop().replace(/^<script>/,'').replace(/<\/script>$/,'').replace(/render\(\);\s*boot\(\);\s*$/,'');
const D=JSON.parse(fs.readFileSync(path.join(ROOT,'data.json'),'utf8'));
const EV=JSON.parse(fs.readFileSync(path.join(__dirname,'cur_event.json'),'utf8'));  // 线上真实：TBD vs TBD

function makeEl(id){return {id,innerHTML:'',textContent:'',style:{},dataset:{},children:[],classList:{add(){},remove(){},contains(){return false}},addEventListener(){},querySelectorAll(){return []},querySelector(){return null},getAttribute(){return null},setAttribute(){},appendChild(){},scrollTo(){},click(){},getBoundingClientRect(){return {width:0,height:0}}}}
let els;
function sim(iso,evOverride){
  const fixed=Date.parse(iso);
  els={'niko-data':makeEl('niko-data')};els['niko-data'].textContent=JSON.stringify(D);
  const document={getElementById(id){return els[id]||(els[id]=makeEl(id))},querySelectorAll(){return []},querySelector(){return null},createElement(){return makeEl('x')},body:makeEl('body'),documentElement:makeEl('html'),addEventListener(){}};
  class FakeDate extends Date{constructor(...a){if(a.length)super(...a);else super(fixed)}static now(){return fixed}}
  const ctx=vm.createContext({document,console,URLSearchParams,Date:FakeDate,Math,JSON,Intl,Promise,Map,Set,String,Number,Array,Object,Boolean,RegExp,Error,TypeError,parseInt,parseFloat,isNaN,encodeURIComponent,decodeURIComponent,window:{scrollTo(){},addEventListener(){},matchMedia:()=>({matches:false,addListener(){}})},matchMedia:()=>({matches:false,addListener(){}}),location:{search:'',pathname:'/index.html',href:'https://x/'},history:{replaceState(){}},navigator:{userAgent:'node'},setTimeout:()=>0,clearTimeout(){},setInterval:()=>0,requestAnimationFrame:()=>0,fetch:()=>Promise.reject(new Error('offline'))});
  vm.runInContext(js,ctx);
  vm.runInContext('FRESH='+JSON.stringify(D)+'; EV_FRESH='+JSON.stringify(evOverride||EV)+'; render();',ctx);
  const h=els.app.innerHTML;
  return {hasCdBox:/id="cdD"/.test(h),hasCdTbd:/class="cd cd-tbd"/.test(h),
    dateLabel:(h.match(/<div class="cd cd-tbd"><div><b>([^<]*)<\/b>/)||[])[1]||null,
    note:(h.match(/<div class="hero-note">([^<]*)<\/div>/)||[])[1]||null,
    preciseTime:/开赛（北京时间）/.test(h), target:vm.runInContext('typeof target!=="undefined"?target:null',ctx)};
}
let fail=0;const ck=(c,m)=>{if(!c){console.log('  ✗ FAIL:',m);fail++}else console.log('  ✓',m)};
console.log('=== 场景1：线上真实 TBD vs TBD（PGL Singapore）===');
const a=sim('2026-11-28T18:37:00+08:00');
console.log(JSON.stringify(a));
ck(!a.hasCdBox,'对手待定时不得显示秒级倒计时方框');
ck(a.hasCdTbd,'对手待定时应显示日期/待定卡片');
ck(a.dateLabel==='11月24日 – 12月13日','应显示赛事日期范围，实际='+a.dateLabel);
ck(a.note==='对手待定 · 开赛时间待公布','说明文案应为「对手待定」，实际='+a.note);
ck(!a.preciseTime,'不得显示精确「开赛（北京时间）」占位时间');
ck(a.target===null,'不得启动倒计时 target');

console.log('\n=== 场景2：真实对阵（Falcons vs Vitality）倒计时照常 ===');
const realEv=JSON.parse(JSON.stringify(EV));
realEv.events=[{id:'real-match',name:'测试赛',short:'测试赛',tier:'S-Tier',status:'upcoming',tag:'next',
  start:'2026-11-29T00:00:00Z',end:'2026-11-29T23:59:59Z',date_text:'Nov 29',
  teams:[{name:'Falcons'},{name:'Vitality'}],schedule:[
    {a:'Falcons',b:'Vitality',ts:Date.parse('2026-11-29T20:00:00+08:00')/1000,bo:'Bo3',round:'决赛',id:'x',sa:null,sb:null}
  ],brackets:[],groups:[]}];
const b=sim('2026-11-29T18:00:00+08:00',realEv);
console.log(JSON.stringify(b));
ck(b.hasCdBox,'真实对阵必须显示倒计时方框');
ck(!b.hasCdTbd,'真实对阵不得显示待定卡片');
ck(els.cdD && /\d/.test(els.cdD.textContent),'真实对阵必须启动倒计时（cdD 有数字）');

console.log(fail?`\nREGRESSION FAILED (${fail})`:'\nALL PASS');
process.exit(fail?1:0);
