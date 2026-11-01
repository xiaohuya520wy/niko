// Pages Function：/gh/<file> 从 Cloudflare KV 读取数据。
// 全量 Cloudflare 管线，不再依赖 GitHub（raw.githubusercontent / jsDelivr 均已移除）。
// 数据由 niko-scheduler Worker 抓取 Liquipedia 后写入 KV（namespace: NikoData）。
// 域名 niko-8u7.pages.dev 国内可达，用户浏览器直连即可拿到分钟级新数据。

const ALLOWED = new Set([
  "event.json",
  "data.json",
  "photos.json",
  "history.json",
  "players.json",
  "player_profile.json",
  "ratings.json",
]);

export async function onRequest(context) {
  const file = context.params.file;
  if (!ALLOWED.has(file)) {
    return new Response(
      JSON.stringify({ error: "file not allowed", allowed: [...ALLOWED] }),
      {
        status: 403,
        headers: { "content-type": "application/json; charset=utf-8" },
      }
    );
  }
  // 部署时用根 wrangler.toml 的 [[kv_namespaces]] binding="NikoData" 注入。
  const kv = context.env && context.env.NikoData;
  if (!kv) {
    return new Response(
      JSON.stringify({ error: "KV binding NikoData 未配置" }),
      {
        status: 500,
        headers: { "content-type": "application/json; charset=utf-8" },
      }
    );
  }
  try {
    const val = await kv.get(file, { type: "text" });
    if (val === null) {
      return new Response(
        JSON.stringify({ error: "KV 中暂无该数据，Worker 正在抓取" }),
        {
          status: 503,
          headers: {
            "content-type": "application/json; charset=utf-8",
            "cache-control": "no-store",
          },
        }
      );
    }
    return new Response(val, {
      status: 200,
      headers: {
        "content-type": "application/json; charset=utf-8",
        // 边缘缓存 120 秒：Worker 每 5 分钟才刷新一次 KV，120s 缓存绝不会比数据更新
        // 周期更旧，却能把 KV 回源压到 ~1/12（前端每 60s 轮询且 fetch 用 no-store，
        // 旧值 10s 会导致每个轮询都击穿到 KV，单常开标签页即可打满免费 10 万次/日额度）。
        "cache-control": "public, max-age=120, s-maxage=120",
        "access-control-allow-origin": "*",
        "x-niko-source": "cloudflare-kv",
      },
    });
  } catch (e) {
    return new Response(JSON.stringify({ error: String(e) }), {
      status: 502,
      headers: {
        "content-type": "application/json; charset=utf-8",
        "cache-control": "no-store",
      },
    });
  }
}
