// /api/stream.js

export default async function handler(req, res) {
  try {
    const target = req.query.url;
    const token = req.query.token;

    // --- Optional Security (bearer token style) ---
    const SERVER_TOKEN = process.env.SERVER_TOKEN || "mysecret";
    if (token !== SERVER_TOKEN) {
      return res.status(403).send("Forbidden");
    }

    if (!target) {
      return res.status(400).send("Missing ?url=");
    }

    const response = await fetch(target, {
      headers: {
        "User-Agent": "Mozilla/5.0"
      }
    });

    if (!response.ok) {
      return res.status(500).send("Stream fetch failed");
    }

    let text = await response.text();

    // --- Fix relative TS segments to absolute
    const base = target.split("/").slice(0, -1).join("/");
    text = text.replace(/^(?!https?:\/\/)(.*\.ts)$/gm, `${base}/$1`);

    res.setHeader("Content-Type", "application/vnd.apple.mpegurl");
    res.send(text);

  } catch (err) {
    res.status(500).send("Error: " + err.message);
  }
}
