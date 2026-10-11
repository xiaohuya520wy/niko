// Pages Function：/gh/<file> 实时代理
// 把 GitHub 仓库里最新的 event.json / data.json / photos.json … 透出来，
// 带 10 秒边缘缓存 + CORS，绕开两层延迟：
//   1) Cloudflare Pages 静态部署是「快照」，refresh.yml 提交新数据后它不会自动变 —— 这里直接读 raw.githubusercontent，永远最新；
//   2) jsDelivr 对 @分支 引用有约 12 小时缓存，前端不再依赖它。
// 这个域名（niko-8u7.pages.dev）国内可达，所以用户浏览器能直接拉到分钟级新数据。

const ALLOWED = new Set([
  "event.json", "data.json", "photos.json", "history.json",
  "players.json", "player_profile.json", "ratings.json",
]);

export async function onRequest(context) {
  const file = context.params.file;
  if (!ALLOWED.has(file)) {
    return new Response(JSON.stringify({ error: "file not allowed", allowed: [...ALLOWED] }), {
      status: 403,
      headers: { "content-type": "application/json; charset=utf-8" },
    });
  }
  const url = `https://raw.githubusercontent.com/xiaohuya520wy/niko/main/${file}`;
  try {
    const r = await fetch(url, {
      cache: "no-store",
      headers: { "User-Agent": "niko-pages-fn" },
    });
    const body = await r.arrayBuffer();
    return new Response(body, {
      status: r.status,
      headers: {
        "content-type": "application/json; charset=utf-8",
        // 边缘缓存 10 秒：既保证用户每次轮询几乎实时，又把对 GitHub 的回源压到最低
        "cache-control": "public, max-age=10, s-maxage=10",
        "access-control-allow-origin": "*",
        "x-niko-source": "github-raw",
      },
    });
  } catch (e) {
    return new Response(JSON.stringify({ error: String(e) }), {
      status: 502,
      headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
    });
  }
}
