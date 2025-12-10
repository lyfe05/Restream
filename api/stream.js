export default async function handler(req, res) {
  try {
    const url = req.query.url;
    const token = req.query.token;

    if (!url) return res.status(400).send("Missing url");

    const SERVER_TOKEN = process.env.SERVER_TOKEN || "mysecret";
    if (token !== SERVER_TOKEN) return res.status(403).send("Forbidden");

    const upstream = await fetch(url, {
      headers: {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://ViberTV-VIP-Secret.com/",
      }
    });

    if (!upstream.ok) {
      return res.status(502).send("Upstream error");
    }

    const contentType = upstream.headers.get("content-type");
    if (contentType) res.setHeader("Content-Type", contentType);

    // If this is a playlist, rewrite ts urls to use your proxy
    if (contentType.includes("mpegurl") || url.endsWith(".m3u8")) {
      const text = await upstream.text();

      const base = url.split("/").slice(0, -1).join("/");

      const rewritten = text.replace(/\n(\/[^\n]+\.ts)/g, (match, rel) => {
        const full = `${base}${rel}`;
        const proxied = `/api/stream?token=${SERVER_TOKEN}&url=${encodeURIComponent(full)}`;
        return `\n${proxied}`;
      });

      return res.send(rewritten);
    }

    // Otherwise, stream binary (ts chunks)
    const reader = upstream.body.getReader();
    async function pump() {
      const { done, value } = await reader.read();
      if (done) return res.end();
      res.write(value);
      return pump();
    }

    return pump();
  } catch (err) {
    return res.status(500).send("Error: " + err.message);
  }
}
