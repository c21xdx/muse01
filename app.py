import json
import os
import socket
import sys
import urllib.request
from datetime import datetime, timezone

from flask import Flask, jsonify, render_template_string

app = Flask(__name__)

UA = {"User-Agent": "velixir-egress-ip/1.0"}


def fetch_json(url, timeout=8):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


_egress = {"fetched_at": None, "data": None, "error": None}


def refresh_egress():
    """Fetch the host's egress IP + geo info. Primary: ip-api.com, fallback: ipify."""
    try:
        data = fetch_json(
            "http://ip-api.com/json/?fields=status,message,country,countryCode,"
            "region,regionName,city,zip,lat,lon,timezone,isp,org,as,query"
        )
        if data.get("status") != "success":
            raise RuntimeError(data.get("message", "ip-api lookup failed"))
        _egress["data"] = data
        _egress["error"] = None
    except Exception as e:
        try:
            req = urllib.request.Request("https://api.ipify.org", headers=UA)
            ip = urllib.request.urlopen(req, timeout=8).read().decode("utf-8").strip()
            _egress["data"] = {"status": "success", "query": ip,
                               "message": "geo unavailable, ipify fallback"}
            _egress["error"] = None
        except Exception as e2:
            _egress["data"] = None
            _egress["error"] = f"ip-api: {e} | ipify: {e2}"
    _egress["fetched_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


refresh_egress()

LABELS = [
    ("query", "出口 IP"),
    ("country", "国家"),
    ("countryCode", "国家代码"),
    ("regionName", "地区"),
    ("city", "城市"),
    ("zip", "邮编"),
    ("timezone", "时区"),
    ("isp", "ISP"),
    ("org", "组织"),
    ("as", "AS 编号"),
]

PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>主机出口 IP 信息</title>
<style>
body{font-family:system-ui,-apple-system,sans-serif;max-width:640px;margin:40px auto;padding:0 16px;color:#222;background:#fafafa}
h1{font-size:20px;margin-bottom:4px}
.ip{font-size:42px;font-weight:800;margin:12px 0;letter-spacing:1px}
table{border-collapse:collapse;width:100%;background:#fff}
td{border:1px solid #e2e2e2;padding:8px 10px;font-size:14px}
td:first-child{color:#777;width:120px}
.err{background:#fff3f3;border:1px solid #f0c0c0;padding:12px;font-size:14px}
.meta{color:#999;font-size:13px;margin-top:16px}
a{color:#06c}
</style>
</head>
<body>
<h1>&#x1F310; 主机出口 IP 信息</h1>
{% if data %}
<div class="ip">{{ data.get('query', '-') }}</div>
<table>
{% for key, label in labels %}
<tr><td>{{ label }}</td><td>{{ data.get(key, '-') }}</td></tr>
{% endfor %}
<tr><td>经纬度</td><td>{{ data.get('lat', '-') }}, {{ data.get('lon', '-') }}</td></tr>
</table>
{% else %}
<div class="err">获取出口 IP 失败：{{ error }}</div>
{% endif %}
<div class="meta">hostname: {{ hostname }} &middot; Python {{ python }} &middot; 数据更新于 {{ fetched_at }} &middot; <a href="/refresh">刷新</a> &middot; <a href="/health">health</a></div>
</body>
</html>"""


@app.route("/")
def index():
    return render_template_string(
        PAGE,
        data=_egress["data"],
        error=_egress["error"],
        labels=LABELS,
        fetched_at=_egress["fetched_at"],
        hostname=socket.gethostname(),
        python=sys.version.split()[0],
    )


@app.route("/refresh")
def refresh():
    refresh_egress()
    return jsonify(_egress)


@app.route("/health")
def health():
    return "ok", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
