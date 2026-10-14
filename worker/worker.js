// worker.js — Endpoint sin caché para el escrutinio 2026 (Cloudflare Workers + KV).
//
//   GET  /datos   -> devuelve el último JSON (Cache-Control: no-store, CORS abierto)
//   PUT  /datos   -> guarda el JSON (requiere  Authorization: Bearer <PUBLISH_TOKEN>)
//
// El secreto PUBLISH_TOKEN se configura con:
//   wrangler secret put PUBLISH_TOKEN

export default {
  async fetch(request, env) {
    const cors = {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, PUT, POST, OPTIONS",
      "Access-Control-Allow-Headers": "Authorization, Content-Type",
      "Cache-Control": "no-store",
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors });
    }

    const url = new URL(request.url);

    if (request.method === "GET") {
      const datos = await env.ESCUTINIO.get("datos");
      return new Response(datos || "{}", {
        status: 200,
        headers: { ...cors, "Content-Type": "application/json" },
      });
    }

    if (request.method === "PUT" || request.method === "POST") {
      const auth = request.headers.get("Authorization") || "";
      if (auth !== `Bearer ${env.PUBLISH_TOKEN}`) {
        return new Response('{"error":"unauthorized"}', {
          status: 401,
          headers: { ...cors, "Content-Type": "application/json" },
        });
      }
      const body = await request.text();
      try {
        JSON.parse(body);
      } catch {
        return new Response('{"error":"invalid json"}', {
          status: 400,
          headers: { ...cors, "Content-Type": "application/json" },
        });
      }
      await env.ESCUTINIO.put("datos", body);
      return new Response('{"ok":true}', {
        status: 200,
        headers: { ...cors, "Content-Type": "application/json" },
      });
    }

    return new Response('{"error":"method not allowed"}', {
      status: 405,
      headers: { ...cors, "Content-Type": "application/json" },
    });
  },
};
