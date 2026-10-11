// niko-scheduler
// 唯一使命：用 Cloudflare 自家可靠 cron（CF 边缘节点跑，不受 GitHub 原生 schedule 延迟/丢弃影响），
// 去派发 GitHub Actions 工作流，让「高频刷新」真正发生。
//
//   - 每 5 分钟派发 refresh.yml  → 重抓进行中赛事、提交 event.json（实时比分/赛程）
//   - 每 6 小时派发 update.yml   → 全量重抓选手资料 + recent_matches，提交 data.json
//
// 注意：本 Worker 跑在 *.workers.dev 上，用户浏览器在国内可能连不上 —— 但这无所谓，
// 因为 cron 是服务端行为，不需要用户访问。真正的「数据代理」放在 niko-8u7.pages.dev
// 的 Pages Function（/gh/<file>），那个域名国内可达。两者分工明确。
//
// 部署：wrangler deploy（见 wrangler.toml）。GitHub Token 用 `wrangler secret put GITHUB_TOKEN` 注入。

const GH_OWNER = "xiaohuya520wy";
const GH_REPO = "niko";
const GH_WORKFLOW_REFRESH = "refresh.yml";
const GH_WORKFLOW_UPDATE = "update.yml";

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(runAll(env, event));
  },

  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (url.pathname === "/trigger") {
      const wf = url.searchParams.get("wf") || GH_WORKFLOW_REFRESH;
      return json(await safe(() => triggerRefresh(env, wf)));
    }
    if (url.pathname === "/health") {
      return json({
        ok: true, name: "niko-scheduler", cron: "*/5 * * * *",
        dispatches: [GH_WORKFLOW_REFRESH, GH_WORKFLOW_UPDATE],
        endpoints: ["/trigger?wf=refresh.yml", "/health"],
      });
    }
    return json({ ok: true, message: "niko-scheduler running (cron-only worker)" });
  },
};

async function runAll(env, event) {
  // 1) 实时比分：每 5 分钟必跑
  await safe(() => triggerRefresh(env, GH_WORKFLOW_REFRESH));
  // 2) 全量资料：每 6 小时跑一次（UTC 整点且分钟 < 6，配合 */5 cron ≈ 每 6h 一次）
  const t = new Date(event.scheduledTime || Date.now());
  if (t.getUTCHours() % 6 === 0 && t.getUTCMinutes() < 6) {
    await safe(() => triggerRefresh(env, GH_WORKFLOW_UPDATE));
  }
}

async function triggerRefresh(env, wf) {
  const owner = env.GH_OWNER || GH_OWNER;
  const repo = env.GH_REPO || GH_REPO;
  const api = `https://api.github.com/repos/${owner}/${repo}/actions/workflows/${wf}/dispatches`;
  const res = await fetch(api, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "Content-Type": "application/json",
      "User-Agent": "niko-cf-scheduler",
      "X-GitHub-Api-Version": "2022-11-28",
    },
    body: JSON.stringify({ ref: "main" }),
  });
  const txt = await res.text();
  return {
    wf,
    dispatch: { status: res.status, ok: res.ok, snipped: txt.slice(0, 200) },
    repo: `${owner}/${repo}`,
    at: new Date().toISOString(),
  };
}

async function safe(fn) {
  try { return await fn(); }
  catch (e) { return { error: String(e) }; }
}

function json(o, status) {
  return new Response(JSON.stringify(o, null, 2), {
    status: status || 200,
    headers: { "Content-Type": "application/json; charset=utf-8", "Access-Control-Allow-Origin": "*" },
  });
}
