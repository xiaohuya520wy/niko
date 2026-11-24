/* 验证：用户手动点 tab 后，KV 刷新不再把选中项拉回深链目标 */
process.env.TZ='Asia/Shanghai';
const fs=require('fs'),vm=require('vm'),path=require('path');
const ROOT=path.join(__dirname,'..');
const html=fs.readFileSync(path.join(ROOT,'event.html'),'utf8');
let js=(html.match(/<script>([\s\S]*?)<\/script>/g)||[]).pop().replace(/^<script>/,'').replace(/<\/script>$/,'').replace(/render\(\);\s*renderWarnBanner\(\);\s*boot\(\);\s*$/,'');
const staleEV=JSON.parse(fs.readFileSync(path.join(ROOT,'event.json'),'utf8'));
const freshEV=JSON.parse(fs.readFileSync(path.join(__dirname,'online_event.json'),'utf8'));
const DATA=JSON.parse(fs.readFileSync(path.join(ROOT,'data.json'),'utf8'));
function makeEl(id){return {id,innerHTML:'',textContent:'',style:{},dataset:{},children:[],classList:{add(){},remove(){},toggle(){},contains(){return false}},addEventListener(){},removeEventListener(){},querySelectorAll(){return []},querySelector(){return null},getAttribute(){return null},setAttribute(){},appendChild(){},scrollTo(){},click(){},getBoundingClientRect(){return {width:0,height:0}}}}
const els={'niko-data':makeEl('niko-data')};els['niko-data'].textContent=JSON.stringify(DATA);
const document={getElementById(id){return els[id]||(els[id]=makeEl(id))},querySelectorAll(){return []},querySelector(){return null},createElement(){return makeEl('x')},body:makeEl('body'),documentElement:makeEl('html'),addEventListener(){}};
const ctx=vm.createContext({document,console,URLSearchParams,Date,Math,JSON,Intl,Promise,Map,Set,String,Number,Array,Object,Boolean,RegExp,Error,TypeError,parseInt,parseFloat,isNaN,encodeURIComponent,decodeURIComponent,location:{search:'?id=pgl-2026-singapore',pathname:'/event.html',href:'https://x/event.html'},history:{replaceState(){}},navigator:{userAgent:'node'},window:{scrollTo(){},addEventListener(){}},matchMedia:()=>({matches:false,addListener(){}}),setTimeout:()=>0,clearTimeout(){},setInterval:()=>0,requestAnimationFrame:()=>0,fetch:()=>Promise.reject(new Error('offline'))});
vm.runInContext(js,ctx);
vm.runInContext('EV_FRESH='+JSON.stringify(freshEV)+'; render();',ctx);
const before=vm.runInContext('CUR',ctx);
vm.runInContext("CUR='blast-rivals-2026-fall'; USER_PICKED=true; render();",ctx);
const picked=vm.runInContext('CUR',ctx);
vm.runInContext('EV_FRESH='+JSON.stringify(freshEV)+'; render();',ctx);   // KV 再次刷新
const after=vm.runInContext('CUR',ctx);
console.log('KV首刷=',before,'| 用户点tab=',picked,'| KV再刷=',after);
let fail=0;
if(before!=='pgl-2026-singapore'){console.log('✗ 首刷应落新赛事');fail++}
if(after!=='blast-rivals-2026-fall'){console.log('✗ FAIL: 用户选择被 KV 刷新覆盖');fail++}
else console.log('✓ PASS: 用户手动选择不被覆盖');
process.exit(fail?1:0);
