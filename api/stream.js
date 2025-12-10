// api/stream.js
export default async function handler(req, res) {
  try {
    const url = req.query.url;
    if (!url) return res.status(400).send("Missing url");

    // You should protect this endpoint in production
    const SERVER_TOKEN = process.env.SERVER_TOKEN || "mysecret";
    const token = req.query.token || req.headers["x-restream-token"];
    if (token !== SERVER_TOKEN) return res.status(403).send("Forbidden");

    // Allow caller to pass explicit headers if upstream checks them.
    // Use query params ?ua=...&ref=... or headers x-proxy-ua/x-proxy-ref
    const overrideUA = req.query.ua || req.headers["x-proxy-ua"];
    const overrideRef = req.query.ref || req.headers["x-proxy-ref"];
    const overrideCookie = req.query.cookie || req.headers["x-proxy-cookie"];

    // Build headers to send upstream. Start from some safe defaults, then override.
    const upstreamHeaders = {
      "user-agent": overrideUA || req.headers["user-agent"] || "Mozilla/5.0",
      "accept": req.headers["accept"] || "*/*",
      "accept-language": req.headers["accept-language"] || "en-US,en;q=0.9",
      "referer": overrideRef || req.headers["referer"] || "",
      "connection": "keep-alive",
    };
    // include cookie if provided by client or override
    if (overrideCookie) upstreamHeaders["cookie"] = overrideCookie;
    else if (req.headers["cookie"]) upstreamHeaders["cookie"] = req.headers["cookie"];

    // Copy incoming auth headers if present (careful with exposing secrets)
    if (req.headers["authorization"]) upstreamHeaders["authorization"] = req.headers["authorization"];

    // Helper to perform streaming fetch + pipe to response
    async function fetchAndPipe(fetchUrl, headers) {
      const upstream = await fetch(fetchUrl, {
        method: "GET",
        headers,
        redirect: "follow" // follow redirects
      });

      // If upstream returns an HTML error page (403/302 with HTML), we want to see that
      if (!upstream.ok) {
        // pass upstream status and headers so client sees reason
        res.status(upstream.status);
        const ct = upstream.headers.get("content-type");
        if (ct) res.setHeader("Content-Type", ct);
        // stream the (likely small) error body
        const body = await upstream.text();
        return res.send(body);
      }

      // Pass the content-type through (important for players)
      const ct = upstream.headers.get("content-type");
      if (ct) res.setHeader("Content-Type", ct);

      // Stream bytes
      const reader = upstream.body.getReader();
      async function pump() {
        const { done, value } = await reader.read();
        if (done) return res.end();
        res.write(value);
        return pump();
      }
      return pump();
    }

    // Try once with the built headers
    const result = await fetchAndPipe(url, upstreamHeaders);

    // (fetchAndPipe will end the response on success or send the error body)
    return;

  } catch (err) {
    console.error("Stream error:", err);
    res.status(500).send("Error: " + err.message);
  }
}
