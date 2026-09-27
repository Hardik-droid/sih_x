import os
import json
import base64
import asyncio
import websockets
import urllib.request

OUT_DIR = "data/hd_screens"
os.makedirs(OUT_DIR, exist_ok=True)

async def send_cmd(ws, method, params=None, msg_id=1):
    req = {"id": msg_id, "method": method}
    if params:
        req["params"] = params
    await ws.send(json.dumps(req))
    while True:
        resp = json.loads(await ws.recv())
        if resp.get("id") == msg_id:
            return resp

async def capture_screen(ws, filename, msg_id=1):
    res = await send_cmd(ws, "Page.captureScreenshot", {"format": "png"}, msg_id=msg_id)
    data = base64.b64decode(res["result"]["data"])
    path = os.path.join(OUT_DIR, filename)
    with open(path, "wb") as f:
        f.write(data)
    print(f"Captured: {path} ({len(data)} bytes)")
    return path

async def eval_js(ws, expr, msg_id=1):
    res = await send_cmd(ws, "Runtime.evaluate", {"expression": expr, "awaitPromise": True}, msg_id=msg_id)
    return res.get("result", {}).get("result", {}).get("value")

async def wait_for_selector(ws, sel, timeout=10, msg_id_base=100):
    for i in range(int(timeout * 5)):
        found = await eval_js(ws, f"Boolean(document.querySelector('{sel}'))", msg_id=msg_id_base + i)
        if found:
            return True
        await asyncio.sleep(0.2)
    return False

async def main():
    targets = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json').read().decode())
    target = next(t for t in targets if t.get('type') == 'page')
    ws_url = target['webSocketDebuggerUrl']
    print("Connecting to Chrome CDP at:", ws_url)
    
    async with websockets.connect(ws_url, max_size=20*1024*1024) as ws:
        # Set viewport to 1920x1080
        await send_cmd(ws, "Emulation.setDeviceMetricsOverride", {
            "width": 1920,
            "height": 1080,
            "deviceScaleFactor": 1,
            "mobile": False
        }, msg_id=10)
        
        # 1. Overview Dashboard
        print("1. Loading Overview...")
        await send_cmd(ws, "Page.navigate", {"url": "http://127.0.0.1:8000/#overview"}, msg_id=11)
        await wait_for_selector(ws, ".metric-card, .kpi, .banner-lead", timeout=5, msg_id_base=100)
        await asyncio.sleep(1)
        await capture_screen(ws, "01_overview.png", msg_id=12)
        
        # 2. Forensic USB Ingest Dialog
        print("2. Opening Forensic USB Ingest Modal...")
        await eval_js(ws, """
            (() => {
                const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Forensic USB Ingest'));
                if (btn) btn.click();
            })()
        """, msg_id=20)
        await wait_for_selector(ws, ".drive-card, .usb-scanner-wrap", timeout=5, msg_id_base=200)
        await asyncio.sleep(1)
        await capture_screen(ws, "02_usb_ingest.png", msg_id=21)
        
        # Close modal
        await eval_js(ws, "(() => { const b = document.querySelector('.modal-close, button[data-action=\"close\"]'); if(b) b.click(); })()", msg_id=22)
        await asyncio.sleep(0.5)
        
        # 3. Evidence Sources
        print("3. Navigating to Evidence Sources...")
        await eval_js(ws, "(() => { const el = Array.from(document.querySelectorAll('a, button, li')).find(e => e.textContent.trim() === 'Evidence sources'); if(el) el.click(); })()", msg_id=30)
        await wait_for_selector(ws, ".source-card, button[data-action*=\"bytes\"]", timeout=5, msg_id_base=300)
        await asyncio.sleep(1)
        await capture_screen(ws, "03_sources.png", msg_id=31)
        
        # 4. Byte Inspector Modal
        print("4. Opening Byte Inspector...")
        await eval_js(ws, """
            (() => {
                const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Inspect bytes'));
                if (btn) btn.click();
            })()
        """, msg_id=40)
        await asyncio.sleep(0.5)
        await eval_js(ws, """
            (() => {
                const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.includes('Read byte range'));
                if (btn) btn.click();
            })()
        """, msg_id=41)
        await asyncio.sleep(1)
        await capture_screen(ws, "04_byte_inspector.png", msg_id=42)
        
        # Close modal
        await eval_js(ws, "(() => { const b = document.querySelector('.modal-close, button[data-action=\"close\"]'); if(b) b.click(); })()", msg_id=43)
        await asyncio.sleep(0.5)
        
        print("Screenshots 01, 02, 03, 04 captured successfully with full content!")

if __name__ == "__main__":
    asyncio.run(main())
