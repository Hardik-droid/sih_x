import urllib.request
import json
import asyncio
import websockets
import base64

async def get_overview():
    targets = json.loads(urllib.request.urlopen('http://127.0.0.1:9222/json').read().decode())
    target = next(t for t in targets if t.get('type') == 'page')
    async with websockets.connect(target['webSocketDebuggerUrl'], max_size=20*1024*1024) as ws:
        js = "(() => { const el = Array.from(document.querySelectorAll('a, button, li')).find(e => e.textContent.trim() === 'Overview'); if(el) el.click(); })()"
        await ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': js}}))
        await ws.recv()
        await asyncio.sleep(1.5)
        await ws.send(json.dumps({'id': 2, 'method': 'Page.captureScreenshot', 'params': {'format': 'png'}}))
        res = json.loads(await ws.recv())
        data = base64.b64decode(res['result']['data'])
        with open('data/hd_screens/01_overview.png', 'wb') as f:
            f.write(data)
        print('01_overview.png captured successfully! Size:', len(data))

if __name__ == '__main__':
    asyncio.run(get_overview())
