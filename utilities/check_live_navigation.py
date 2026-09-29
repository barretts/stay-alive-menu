"""Local Chrome DevTools check using only Python's standard library."""
import pathlib,subprocess,json,time,socket,struct,base64,os,urllib.request
W=pathlib.Path(__file__).parent;PROFILE=W/'chrome-menu-live-profile'
class CDP:
 def __init__(self,url):
  from urllib.parse import urlsplit
  u=urlsplit(url);self.sock=socket.create_connection((u.hostname,u.port),timeout=8);self.buffer=bytearray();self.id=0
  key=base64.b64encode(os.urandom(16)).decode();self.sock.sendall(f'GET {u.path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n'.encode())
  while b'\r\n\r\n' not in self.buffer:self.buffer+=self.sock.recv(4096)
  header,rest=self.buffer.split(b'\r\n\r\n',1);assert b'101' in header,header;self.buffer=bytearray(rest)
 def read(self,n):
  while len(self.buffer)<n:
   d=self.sock.recv(65536)
   if not d:raise EOFError()
   self.buffer+=d
  d=bytes(self.buffer[:n]);del self.buffer[:n];return d
 def call(self,method,params=None):
  self.id+=1;data=json.dumps({'id':self.id,'method':method,'params':params or {}}).encode();mask=os.urandom(4);n=len(data)
  header=bytes([0x81,0x80|n]) if n<126 else bytes([0x81,0xfe])+struct.pack('>H',n)
  self.sock.sendall(header+mask+bytes(v^mask[i%4] for i,v in enumerate(data)))
  while True:
   a,b=self.read(2);n=b&127
   if n==126:n=struct.unpack('>H',self.read(2))[0]
   if n==127:n=struct.unpack('>Q',self.read(8))[0]
   mask=self.read(4) if b&128 else None;raw=self.read(n)
   if mask:raw=bytes(v^mask[i%4] for i,v in enumerate(raw))
   if a&15==8:raise RuntimeError('Chrome closed the WebSocket: '+repr(raw))
   if a&15!=1:continue
   message=json.loads(raw)
   if message.get('id')==self.id:
    if 'error' in message:raise RuntimeError(message['error'])
    return message.get('result')
 def js(self,expr,user_gesture=True,await_promise=False):
  result=self.call('Runtime.evaluate',{'expression':expr,'returnByValue':True,'userGesture':user_gesture,'awaitPromise':await_promise})
  if 'exceptionDetails' in result:raise RuntimeError(result['exceptionDetails'])
  return result['result'].get('value')
def main():
 PROFILE.mkdir(exist_ok=True)
 proc=subprocess.Popen([r'C:\Program Files\Google\Chrome\Application\chrome.exe','--headless=new','--disable-gpu','--do-not-de-elevate','--no-first-run','--allow-file-access-from-files','--autoplay-policy=no-user-gesture-required','--remote-debugging-port=0','--user-data-dir='+str(PROFILE),pathlib.Path(r'D:\StayAlive\MenuArchive\index.html').as_uri()],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 client=None
 try:
  for _ in range(60):
   portfile=PROFILE/'DevToolsActivePort'
   if portfile.exists():break
   time.sleep(.1)
  port=int(portfile.read_text().splitlines()[0]);pages=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list'));client=CDP(next(p['webSocketDebuggerUrl'] for p in pages if p['type']=='page'))
  for _ in range(50):
   if client.js("typeof menuNav !== 'undefined' && document.readyState==='complete'"):break
   time.sleep(.1)
  print('Ready',flush=True)
  client.js("openAsset(byId.get('VTS01_VOB40_CELL01'));$('hotspots').querySelector('[data-button=\"8\"]').click();true")
  time.sleep(4)
  media=client.js("({asset:current.id,time:$('video').currentTime,readyState:$('video').readyState,paused:$('video').paused,error:$('video').error?.message||null})")
  print('Bonus transition',media,flush=True)
  assert media['asset']=='VTS01_VOB08_CELL01',media
  assert media['readyState']>=2 and not media['error'],media
  client.js("$('hotspots').querySelector('[data-button=\"3\"]').click();true")
  assert client.js('current.id')=='VTS01_VOB40_CELL01'
  client.js("$('hotspots').querySelector('[data-button=\"9\"]').click();$('hotspots').querySelector('[data-button=\"1\"]').click();true")
  assert client.js('current.id')=='VTS01_VOB09_CELL01'
  client.js('history.back();true');time.sleep(.25)
  assert client.js('current.id')=='VTS01_VOB12_CELL01'
  client.js('history.forward();true');time.sleep(.25)
  assert client.js('current.id')=='VTS01_VOB09_CELL01'
  screenshot=client.call('Page.captureScreenshot',{'format':'png'})['data'];(W/'linked-menu-live.png').write_bytes(base64.b64decode(screenshot))
  result={'status':'passed','automatic_bonus_transition':media,'browser_back_forward':True};(W/'live-navigation-result.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
 finally:
  if client:
   try:client.call('Browser.close')
   except Exception:pass
  try:proc.wait(timeout=5)
  except subprocess.TimeoutExpired:proc.terminate()

if __name__=='__main__':main()
