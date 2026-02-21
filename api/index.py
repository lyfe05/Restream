from flask import Flask, request, Response
from flask_cors import CORS
import requests
import re
from urllib.parse import urljoin, quote, unquote
import traceback

app = Flask(__name__)
CORS(app)

HEADERS = {
    "Referer": "https://streameeeeee.site/",
    "Origin": "https://streameeeeee.site",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*"
}

@app.route('/')
def proxy():
    target_url = request.args.get('url')
    if not target_url:
        return "Missing ?url= parameter", 400
    
    try:
        # Decode URL if it's encoded
        target_url = unquote(target_url)
        
        # Fetch upstream (disable SSL verify for weird ports/servers)
        resp = requests.get(
            target_url, 
            headers=HEADERS, 
            timeout=30, 
            stream=True,
            verify=False  # Disable SSL verification for problematic servers
        )
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
            # Read text content
            text = resp.text
            
            # Build proxy base URL (scheme + host + /)
            proxy_base = f"{request.scheme}://{request.host}/"
            
            # Get base path for resolving relative URLs
            base_path = target_url.rsplit('/', 1)[0] + '/'
            
            lines = []
            for line in text.splitlines():
                stripped = line.strip()
                
                # Handle HLS tags with URIs
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
                
                # Empty lines
                elif not stripped:
                    lines.append(line)
                
                # Media lines (URLs)
                else:
                    if stripped.startswith('http'):
                        abs_url = stripped
                    else:
                        abs_url = urljoin(base_path, stripped)
                    
                    # Rewrite to proxy
                    proxy_url = f"{proxy_base}?url={quote(abs_url, safe='')}"
                    lines.append(proxy_url)
            
            output = '\n'.join(lines)
            
            return Response(
                output,
                mimetype='application/vnd.apple.mpegurl',
                headers={'Cache-Control': 'no-cache'}
            )
        
        else:
            # Binary stream (video segments)
            def generate():
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        yield chunk
            
            return Response(
                generate(),
                mimetype=content_type or 'video/MP2T',
                direct_passthrough=True
            )
            
    except Exception as e:
        # Return detailed error for debugging
        error_msg = f"Error: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        print(error_msg)  # Log to console
        return error_msg, 500

if __name__ == '__main__':
    # Disable SSL warnings
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    app.run(host='0.0.0.0', port=8000, threaded=True, debug=True)
