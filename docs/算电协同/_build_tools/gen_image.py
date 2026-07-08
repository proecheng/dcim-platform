#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 curl 调 micuapi gpt-image-2-pro（urllib 被 Cloudflare 1010 拦，curl 可通过）。"""
import sys, json, os, base64, subprocess, tempfile, time

API_URL = "https://www.micuapi.ai/v1/images/generations"
API_KEY = os.environ.get("MICUAPI_KEY") or "sk-<在此填入你的_micuapi_KEY>"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

def curl_post(body):
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(body, f, ensure_ascii=False); f.close()
    try:
        p = subprocess.run(
            ["curl", "-s", "--max-time", "600", "-X", "POST", API_URL,
             "-H", "Authorization: Bearer " + API_KEY,
             "-H", "Content-Type: application/json",
             "-A", UA, "--data-binary", "@" + f.name],
            capture_output=True, text=True, encoding="utf-8")
        return p.stdout
    finally:
        os.unlink(f.name)

def curl_download(url, out):
    subprocess.run(["curl", "-s", "--max-time", "600", "-A", UA, "-o", out, url], check=True)

def gen(prompt, out, size):
    raw = curl_post({"model": "gpt-image-2-pro", "prompt": prompt, "n": 1, "size": size})
    data = json.loads(raw)
    item = data["data"][0]
    if item.get("b64_json"):
        open(out, "wb").write(base64.b64decode(item["b64_json"]))
    elif item.get("url"):
        curl_download(item["url"], out)
    else:
        raise RuntimeError("no image field: " + raw[:400])
    sz = os.path.getsize(out)
    if sz < 1000:
        raise RuntimeError("file too small %d" % sz)
    return sz

def one(out, prompt, size, retries=3):
    for attempt in range(1, retries + 1):
        try:
            sz = gen(prompt, out, size)
            print("OK", os.path.basename(out), size, sz, flush=True); return True
        except Exception as e:
            print("TRY%d-FAIL" % attempt, os.path.basename(out), repr(e)[:200], flush=True)
            if attempt < retries:
                time.sleep(6 * attempt)
    print("ERR", os.path.basename(out), "gave up", flush=True); return False

if __name__ == "__main__":
    if sys.argv[1] == "--batch":
        figs = json.load(open(sys.argv[2], encoding="utf-8"))
        ok = 0
        for fig in figs:
            out = fig["out"]
            if os.path.exists(out) and os.path.getsize(out) > 1000:
                print("SKIP", os.path.basename(out), flush=True); ok += 1; continue
            if one(out, fig["prompt"], fig.get("size", "1536x1024")):
                ok += 1
            time.sleep(4)
        print("DONE", ok, "/", len(figs), flush=True)
    else:
        one(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "1536x1024")
