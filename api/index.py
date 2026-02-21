from flask import Flask, request, Response
from flask_cors import CORS
import requests
import re
from urllib.parse import urljoin, quote, unquote
import traceback

app = Flask(__name__)
CORS(app)

# EXACT headers from your JSON (preserve the trailing spaces!)
HEADERS = {
    "Referer": "https://streameeeeee.site/ ",  # Note the space at end
    "Origin": "https://streameeeeee.site ",    # Note the space at end
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",  # No compression
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "cross-site"
}

@app.route('/')
def proxy():
    target_url = request.args.get('url')
    if not target_url:
        return "Missing ?url= parameter", 400
    
    try:
        # Decode if double-encoded
        if '%' in target_url:
            try:
                target_url = unquote(target_url)
            except:
                pass
        
        # Create session to handle cookies/redirects better
        session = requests.Session()
        
        # Fetch upstream
        resp = session.get(
            target_url, 
            headers=HEADERS, 
            timeout=30, 
            stream=True,
            verify=False,
            allow_redirects=True
        )
        
        # Debug: Print what we got
        print(f"URL: {target_url}")
        print(f"Status: {resp.status_code}")
        print(f"Response headers: {dict(resp.headers)}")
        
        if resp.status_code == 403:
            # Return debug info to see what's happening
            return f"""
            403 Forbidden - CDN blocked request.
            
            URL attempted: {target_url}
            Headers sent: {HEADERS}
            
            Response headers: {dict(resp.headers)}
            
            Possible causes:
            1. Token expired (URLs are time-limited)
            2. IP-locked token (token was generated for different IP)
            3. Missing cookies/session
            """, 403
        
        resp.raise_for_status()
        
        content_type = resp.headers.get('Content-Type', '').lower()
        
        # Check if M3U8
        is_m3u8 = (
            'mpegurl' in content_type or 
            'm3u8' in content_type or
            target_url.endswith('.m3u8') or 
            target_url.endswith('.m3u')
        )
        
        if is_m3u8:
            text = resp.text
            
            # Build proxy base URL
            scheme = request.headers.get('X-Forwarded-Proto', request.scheme)
            host = request.headers.get('X-Forwarded-Host', request.host)
            proxy_base = f"{scheme}://{host}/"
            
            base_path = target_url.rsplit('/', 1)[0] + '/'
            
            lines = []
            for line in text.splitlines():
                stripped = line.strip()
                
                if stripped.startswith('#'):
                    if 'URI="' in stripped:
                        def replace_uri(match):
                            uri = match.group(1)
                            if uri.startswith('http'):
                                abs_uri = uri
                            else:
                                abs_uri = urljoin(base_path, uri)
                            return f'URI="{proxy_base}?url={quote(abs_uri, safe="")}"'
                        
                        line = re.sub(r'URI="([^"]+)"', replace_uri, line)
                    lines.append(line)
                
                elif not stripped:
                    lines.append(line)
                
                else:
                    if stripped.startswith('http'):
                        abs_url = stripped
                    else:
                        abs_url = urljoin(base_path, stripped)
                    
                    proxy_url = f"{proxy_base}?url={quote(abs_url, safe='')}"
                    lines.append(proxy_url)
            
            output = '\n'.join(lines)
            
            return Response(
                output,
                mimetype='application/vnd.apple.mpegurl',
                headers={'Cache-Control': 'no-cache'}
            )
        
        else:
            # Binary stream
            def generate():
                for chunk in resp.iter_content(chunk_size=16384):
                    if chunk:
                        yield chunk
            
            return Response(
                generate(),
                mimetype=content_type or 'video/MP2T',
                direct_passthrough=True
            )
            
    except Exception as e:
        error_msg = f"Error: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        print(error_msg)
        return error_msg, 500

if __name__ == '__main__':
    import urllib3
    urllib3.disable_warnings()
    app.run(host='0.0.0.0', port=8000, threaded=True, debug=True)
