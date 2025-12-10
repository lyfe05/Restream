export default async function handler(req, res) {
  try {
    const url = req.query.url;
    const token = req.query.token;

    if (!url) return res.status(400).send("Missing url");

    const SERVER_TOKEN = process.env.SERVER_TOKEN || "mysecret";
    if (token !== SERVER_TOKEN) {
      return res.status(403).send("Forbidden");
    }

    // Fetch with streaming
    const upstream = await fetch(url, {
      headers: {
        "User-Agent": "Mozilla/5.0",
        "Connection": "keep-alive",
        "Accept": "*/*"
      }
    });

    if (!upstream.ok) {
      return res.status(502).send("Upstream error");
    }

    // Pass content-type from Xtream (VERY IMPORTANT!)
    const contentType = upstream.headers.get("content-type");
    if (contentType) res.setHeader("Content-Type", contentType);

    // Pipe raw stream bytes directly
    const reader = upstream.body.getReader();
    const encoder = res;

    async function pump() {
      const { done, value } = await reader.read();
      if (done) return res.end();
      encoder.write(value);
      return pump();
    }

    return pump();
  } catch (err) {
    return res.status(500).send("Error: " + err.message);
  }
}
