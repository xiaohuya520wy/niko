/* 检查首页 hero 卡片 href 是否指向最新赛事（旧内联 + KV 新数据） */
process.env.TZ='Asia/Shanghai';
const fs=require('fs'),vm=require('vm'),path=require('path');
const ROOT=path.join(__dirname,'..');
const html=fs.readFileSync(path.join(ROOT,'index.html'),'utf8');
const js=(html.match(/<script>([\s\S]*?)<\/script>/g)||[]).pop().replace(/^<script>/,'').replace(/<\/script>$/,'').replace(/render\(\);\s*boot\(\);\s*$/,'');
const DATA=JSON.parse(fs.readFileSync(path.join(__dirname,'online_data.json'),'utf8'));
const staleEV=JSON.parse(fs.readFileSync(path.join(ROOT,'event.json'),'utf8'));
const freshEV=JSON.parse(fs.readFileSync(path.join(__dirname,'online_event.json'),'utf8'));
function makeEl(id){return {id,innerHTML:'',textContent:'',style:{},dataset:{},children:[],classList:{add(){},remove(){},toggle(){},contains(){return false}},addEventListener(){},querySelectorAll(){return []},querySelector(){return null},getAttribute(){return null},setAttribute(){},appendChild(){},scrollTo(){},click(){},getBoundingClientRect(){return {width:0,height:0}}}}
function run(useFresh,iso){
 const fixed=Date.parse(iso);
 const els={'niko-data':makeEl('niko-data')};els['niko-data'].textContent=JSON.stringify(DATA);
 const document={getElementById(id){return els[id]||(els[id]=makeEl(id))},querySelectorAll(){return []},querySelector(){return null},createElement(){return makeEl('x')},body:makeEl('body'),documentElement:makeEl('html'),addEventListener(){}};
 class FakeDate extends Date{constructor(...a){if(a.length)super(...a);else super(fixed)}static now(){return fixed}}
 const ctx=vm.createContext({document,console,URLSearchParams,Date:FakeDate,Math,JSON,Intl,Promise,Map,Set,String,Number,Array,Object,Boolean,RegExp,Error,TypeError,parseInt,parseFloat,isNaN,encodeURIComponent,decodeURIComponent,window:{scrollTo(){},addEventListener(){},matchMedia:()=>({matches:false,addListener(){}})},matchMedia:()=>({matches:false,addListener(){}}),location:{search:'',pathname:'/index.html',href:'https://x/'},history:{replaceState(){}},navigator:{userAgent:'node'},setTimeout:()=>0,clearTimeout(){},setInterval:()=>0,requestAnimationFrame:()=>0,fetch:()=>Promise.reject(new Error('offline'))});
 vm.runInContext(js,ctx);
 vm.runInContext('FRESH='+JSON.stringify(DATA)+'; EV_FRESH='+JSON.stringify(useFresh?freshEV:staleEV)+'; render();',ctx);
 const h=els.app.innerHTML;
 const href=(h.match(/<a class="hero hero-link" href="([^"]+)"/)||[])[1];
 const tag=(h.match(/<span class="tag">([^<]*)<\/span>/)||[])[1];
 return {tag,href,hasNew:(h.match(/PGL Major Singapore 2026/g)||[]).length};
}
const iso='2026-11-24T09:33:00+08:00';
const a=run(false,iso),b=run(true,iso);
console.log('旧内联 :',JSON.stringify(a));
console.log('KV新数据:',JSON.stringify(b));
let fail=0;
if(b.href!=='event.html?id=pgl-2026-singapore'){console.log('✗ FAIL: hero 链接应指向 pgl-2026-singapore，实际',b.href);fail++}
else console.log('✓ PASS: KV 刷新后 hero 链接指向最新赛事');
process.exit(fail?1:0);
