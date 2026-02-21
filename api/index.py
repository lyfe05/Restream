from flask import Flask, request, Response
from flask_cors import CORS
import requests
import re
from urllib.parse import urljoin, quote

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Enable CORS for all routes

HEADERS = {
    "Referer": "https://streameeeeee.site/",
    "Origin": "https://streameeeeee.site",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*"
}

@app.route('/')
def proxy():
    url = request.args.get('url')
    if not url:
        return "Missing ?url= parameter", 400
    
    try:
        # Fetch from upstream
        resp = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        resp.raise_for_status()
        
        content_type = resp.headers.get('Content-Type', '')
        
        # Check if M3U8 playlist
        is_m3u8 = ('mpegurl' in content_type or 
                   url.endswith('.m3u8') or 
                   url.endswith('.m3u'))
        
        if is_m3u8:
            text = resp.text
            base = url.rsplit('/', 1)[0] + '/'
            proxy_base = request.base_url  # e.g., http://localhost:8000/
            
            lines = []
            for line in text.splitlines():
                stripped = line.strip()
                
                # Keep comments but rewrite URIs inside them
                if stripped.startswith('#'):
                    if 'URI="' in line:
                        line = re.sub(
                            r'URI="([^"]+)"',
                            lambda m: f'URI="{proxy_base}?url={quote(urljoin(base, m.group(1)) if not m.group(1).startswith("http") else m.group(1), safe="")}"',
                            line
                        )
                    lines.append(line)
                elif not stripped:
                    lines.append(line)
                else:
                    # Media segment or sub-playlist URL
                    if stripped.startswith('http'):
                        abs_url = stripped
                    else:
                        abs_url = urljoin(base, stripped)
                    
                    # Rewrite to use this proxy
                    proxy_url = f"{proxy_base}?url={quote(abs_url, safe='')}"
                    lines.append(proxy_url)
            
            body = '\n'.join(lines)
            return Response(body, mimetype='application/vnd.apple.mpegurl')
        
        else:
            # Binary content (video segments) - stream it
            def generate():
                for chunk in resp.iter_content(chunk_size=8192):
                    yield chunk
            
            return Response(generate(), mimetype=content_type)
            
    except Exception as e:
        return f"Proxy error: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, threaded=True)
