# -*- coding: utf-8 -*-
"""按页号生成PPT页面图：有参照图用edits(带原图参考)，无则用generations。
   用法：MICUAPI_KEY=... python gen_ppt.py 3 4   (每次≤2页)"""
import sys, json, os, base64, subprocess, tempfile, time
KEY = os.environ.get('MICUAPI_KEY', '')
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
GEN = 'https://www.micuapi.ai/v1/images/generations'
EDIT = 'https://www.micuapi.ai/v1/images/edits'
PICS = r'D:\mytest1\docs\算电协同\pics'
PJSON = r'D:\mytest1\docs\算电协同\ppt\_prompts.json'
P = {p['page']: p for p in json.load(open(PJSON, encoding='utf-8'))}

def _run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', **kw).stdout

def _dl(url, out):
    subprocess.run(['curl', '-s', '--max-time', '300', '-A', UA, '-o', out, url], check=True)

def gen_one(page):
    p = P[page]; out = p['out']; figs = p.get('ref_figs', [])
    pf = tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False, encoding='utf-8')
    pf.write(p['prompt']); pf.close()
    try:
        if figs:  # 图生图：主参照图 figs[0]
            bn = os.path.basename(figs[0])
            cmd = ['curl', '-s', '--max-time', '300', '-X', 'POST', EDIT,
                   '-H', 'Authorization: Bearer ' + KEY, '-A', UA,
                   '-F', 'model=gpt-image-2-pro', '-F', 'size=' + p['size'],
                   '-F', 'image=@' + bn, '-F', 'prompt=<' + pf.name]
            raw = _run(cmd, cwd=PICS)
        else:  # 纯文生图
            body = {'model': 'gpt-image-2-pro', 'prompt': p['prompt'], 'n': 1, 'size': p['size']}
            jf = tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8')
            json.dump(body, jf, ensure_ascii=False); jf.close()
            cmd = ['curl', '-s', '--max-time', '300', '-X', 'POST', GEN,
                   '-H', 'Authorization: Bearer ' + KEY, '-H', 'Content-Type: application/json',
                   '-A', UA, '--data-binary', '@' + jf.name]
            raw = _run(cmd); os.unlink(jf.name)
        try:
            item = json.loads(raw)['data'][0]
        except Exception:
            return 'FAIL:' + raw[:80].replace('\n', ' ')
        if item.get('b64_json'):
            open(out, 'wb').write(base64.b64decode(item['b64_json']))
        elif item.get('url'):
            _dl(item['url'], out)
        else:
            return 'FAIL:nofield'
        sz = os.path.getsize(out)
        return ('OK %d' % sz) if sz > 1000 else 'FAIL:small'
    finally:
        os.unlink(pf.name)

if __name__ == '__main__':
    assert KEY, 'no MICUAPI_KEY'
    for a in sys.argv[1:]:
        page = int(a)
        mode = 'edits' if P[page].get('ref_figs') else 'gen'
        for att in range(1, 6):
            r = gen_one(page)
            if r.startswith('OK'):
                print('page-%02d [%s] %s' % (page, mode, r), flush=True); break
            print('page-%02d [%s] try%d %s' % (page, mode, att, r), flush=True); time.sleep(8)
        else:
            print('page-%02d GAVEUP' % page, flush=True)
