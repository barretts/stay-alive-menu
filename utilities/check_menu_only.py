"""Real Chrome checks for both views, including restricted audible autoplay.

Only test profiles are launched. Runtime inspection does not grant user gestures;
clicks, touch taps, and keyboard input are dispatched as real browser input.
Reports and screenshots go to a temporary directory printed at completion.
"""
import base64
import argparse
import json
import pathlib
import subprocess
import tempfile
import time
import urllib.request
from check_live_navigation import CDP

ROOT=pathlib.Path(__file__).resolve().parent.parent
URL=(ROOT/'index.html').as_uri()
CHROME=r'C:\Program Files\Google\Chrome\Application\chrome.exe'


class BrowserCheck:
 def __init__(self,output,name,flags=()):
  profile=output/(name+'-profile');profile.mkdir()
  self.chrome_log=(output/(name+'-chrome.log')).open('wb')
  self.proc=subprocess.Popen([CHROME,'--headless=new','--disable-gpu','--do-not-de-elevate','--no-first-run','--no-default-browser-check','--window-size=1280,800','--remote-debugging-port=0','--user-data-dir='+str(profile),*flags,'about:blank'],stdout=subprocess.DEVNULL,stderr=self.chrome_log)
  self.client=None
  try:
   portfile=profile/'DevToolsActivePort'
   deadline=time.monotonic()+10
   while not portfile.exists():
    if self.proc.poll() is not None:raise RuntimeError('Chrome exited before connecting')
    if time.monotonic()>deadline:raise TimeoutError('Chrome connection timed out')
    time.sleep(.1)
   port=int(portfile.read_text().splitlines()[0])
   pages=json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list'))
   self.client=CDP(next(p['webSocketDebuggerUrl'] for p in pages if p['type']=='page'))
   self.client.call('Page.enable')
   self.client.call('Emulation.setFocusEmulationEnabled',{'enabled':True})
   self.client.call('Page.addScriptToEvaluateOnNewDocument',{'source':"window.checkErrors=[];addEventListener('error',e=>checkErrors.push(e.message));addEventListener('unhandledrejection',e=>checkErrors.push(String(e.reason)));"})
  except Exception:
   self.close()
   raise

 def js(self,expression,await_promise=False):
  return self.client.js(expression,user_gesture=False,await_promise=await_promise)

 def wait(self,condition,timeout=8):
  deadline=time.monotonic()+timeout
  while time.monotonic()<deadline:
   if self.js(condition):return
   time.sleep(.1)
  raise AssertionError('Timed out: '+condition+'; state='+str(self.js("typeof current==='undefined'?null:({asset:current?.id,paused:$('video').paused,muted:$('video').muted,error:$('menuStatus').textContent})")))

 def navigate(self,url):
  self.client.call('Page.navigate',{'url':url})
  self.wait("location.href.split('#')[0]==="+json.dumps(url.split('#')[0])+" && document.readyState==='complete' && typeof menuNav!=='undefined'")

 def playing(self,asset=None,timeout=8):
  self.wait("current && !$('video').paused && $('video').readyState>=2 && $('video').currentTime>0"+(" && current.id==="+json.dumps(asset) if asset else ''),timeout=timeout)

 def click(self,selector,touch=False):
  point=self.js("(()=>{const e=document.querySelector("+json.dumps(selector)+");if(!e)throw Error('Missing control');const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2}})()")
  if touch:
   self.client.call('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{**point,'id':1}]})
   self.client.call('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
  else:
   self.client.call('Input.dispatchMouseEvent',{'type':'mouseMoved',**point})
   self.client.call('Input.dispatchMouseEvent',{'type':'mousePressed',**point,'button':'left','clickCount':1})
   self.client.call('Input.dispatchMouseEvent',{'type':'mouseReleased',**point,'button':'left','clickCount':1})

 def key(self,key,number):
  for kind in ('keyDown','keyUp'):
   params={'type':kind,'key':key,'code':key,'windowsVirtualKeyCode':number}
   if kind=='keyDown' and key=='Enter':params.update(text='\r',unmodifiedText='\r')
   self.client.call('Input.dispatchKeyEvent',params)

 def layout(self):
  result=self.js("""(()=>{
   const stage=$('stage').getBoundingClientRect(),b=current.button_states[0]?.buttons.find(b=>b.group===wideGroup(current)),h=b&&$('hotspots').querySelector(`[data-button="${b.number}"]`).getBoundingClientRect();
   return {width:innerWidth,height:innerHeight,x:stage.x,y:stage.y,w:stage.width,h:stage.height,controls:$('video').controls,header:getComputedStyle(document.querySelector('header')).display,aside:getComputedStyle(document.querySelector('aside')).display,scroll:document.documentElement.scrollWidth>innerWidth,hotspot:!b||Math.abs(h.x-stage.x-b.bbox[0]/720*stage.width)<1&&Math.abs(h.y-stage.y-b.bbox[1]/480*stage.height)<1};
  })()""")
  assert result['header']=='none' and result['aside']=='none' and not result['controls'],result
  assert not result['scroll'] and result['hotspot'],result
  assert result['x']>=-.1 and result['y']>=-.1 and result['x']+result['w']<=result['width']+.1 and result['y']+result['h']<=result['height']+.1,result
  assert abs(result['w']/result['h']-16/9)<.001,result
  return result

 def screenshot(self,path):
  self.wait("getComputedStyle($('menuControls')).opacity==='0'")
  path.write_bytes(base64.b64decode(self.client.call('Page.captureScreenshot',{'format':'png'})['data']))

 def no_errors(self):
  assert self.js('checkErrors')==[],self.js('checkErrors')

 def close(self):
  if self.client:
   try:self.client.call('Browser.close')
   except (EOFError,OSError,RuntimeError,ValueError):pass
   self.client.sock.close()
  if self.proc.poll() is None:
   try:self.proc.wait(timeout=5)
   except subprocess.TimeoutExpired:self.proc.terminate()
  self.chrome_log.close()


def check_normal(output):
 browser=BrowserCheck(output,'normal')
 try:
  browser.navigate(URL+'?view=menu')
  browser.playing('VTS01_VOB40_CELL01')
  first=browser.js("({muted:$('video').muted,unlockSound,loop:$('video').loop,history:history.state.menuArchive})")
  assert first['loop'] and first['history'],first
  browser.layout()
  browser.screenshot(output/'menu-desktop.png')
  browser.js("$('video').currentTime=$('video').duration-.25;true")
  browser.wait("$('video').currentTime<2 && !$('video').paused")
  browser.click('#hotspots [data-button="9"]')
  browser.playing('VTS01_VOB12_CELL01')
  assert not browser.js("$('video').muted"),'First real click enables sound'
  browser.click('#hotspots [data-button="1"]')
  browser.playing('VTS01_VOB09_CELL01')
  browser.js('history.back();true')
  browser.playing('VTS01_VOB12_CELL01')
  assert browser.js('menuOnly && (menuNav.s[8]>>10)===1'),'Back restores view and selection'
  browser.js('history.forward();true')
  browser.playing('VTS01_VOB09_CELL01')
  browser.click('#hotspots [data-button="5"]')
  browser.playing('VTS01_VOB12_CELL01')
  browser.click('#hotspots [data-button="4"]')
  browser.playing('VTS01_VOB40_CELL01')
  browser.js("$('hotspots').querySelector('[data-button=\"1\"]').focus();true")
  browser.key('ArrowDown',40)
  assert browser.js('document.activeElement.dataset.button')=='2','Arrow keys follow the DVD directional links'
  browser.key('Enter',13)
  assert browser.js('current.id')=='VTS01_VOB43_CELL01',browser.js("({asset:current.id,register:menuNav.g[9],selected:menuNav.s[8]>>10})")
  browser.playing('VTS01_VOB43_CELL01')
  browser.click('#soundToggle')
  assert browser.js("$('video').muted && !unlockSound"),'Explicit mute is retained'
  browser.click('#hotspots [data-button="2"]')
  browser.playing()
  assert browser.js("$('video').muted"),'Navigation respects explicit mute'
  browser.click('#soundToggle')
  browser.playing()
  assert not browser.js("$('video').muted")
  browser.navigate(URL+'?view=menu#asset=VTS01_VOB40_CELL01')
  browser.playing('VTS01_VOB40_CELL01')
  browser.click('#hotspots [data-button="8"]')
  browser.playing('VTS01_VOB08_CELL01')
  browser.click('#hotspots [data-button="3"]')
  browser.playing('VTS01_VOB40_CELL01')
  browser.click('#hotspots [data-button="6"]')
  browser.wait("!$('titlePanel').hidden")
  assert browser.js("$('video').paused && (localArchive ? $('targetLinks').querySelector('a').getAttribute('href').includes('StayAlive_1080p') : !$('targetLinks').children.length && $('targetInfo').textContent.includes('not included'))"),'Movie destination is handled correctly for local and hosted views'
  browser.click('#returnToMenu')
  browser.playing('VTS01_VOB40_CELL01')
  browser.client.call('Page.reload')
  browser.wait("document.readyState==='complete' && typeof menuNav!=='undefined' && current?.id==='VTS01_VOB40_CELL01'")
  browser.playing('VTS01_VOB40_CELL01')
  browser.client.call('Emulation.setDeviceMetricsOverride',{'width':390,'height':844,'deviceScaleFactor':1,'mobile':True})
  browser.client.call('Emulation.setTouchEmulationEnabled',{'enabled':True})
  mobile=browser.layout()
  browser.screenshot(output/'menu-mobile.png')
  browser.click('#hotspots [data-button="9"]',touch=True)
  browser.playing('VTS01_VOB12_CELL01')
  browser.client.call('Emulation.setDeviceMetricsOverride',{'width':844,'height':390,'deviceScaleFactor':1,'mobile':True})
  landscape=browser.layout()
  browser.no_errors()
  return {'initial_playback':first,'mobile':mobile,'landscape':landscape,'navigation_history_keyboard_touch_transitions_external_return':'passed'}
 finally:browser.close()


def check_restricted(output):
 browser=BrowserCheck(output,'restricted',['--autoplay-policy=document-user-activation-required','--disable-features=PreloadMediaEngagementData,MediaEngagementBypassAutoplayPolicies'])
 try:
  browser.navigate(URL+'?view=menu')
  browser.playing('VTS01_VOB40_CELL01')
  assert browser.js("$('video').muted && unlockSound && $('playMenu').hidden"),'Blocked audio falls back to moving muted video'
  browser.click('#hotspots [data-button="2"]')
  browser.playing('VTS01_VOB43_CELL01')
  assert not browser.js("$('video').muted || unlockSound"),'Trusted menu selection unlocks audio'
  browser.click('#archiveView')
  browser.wait("!menuOnly && !$('detail').open && $('grid').children.length>0")
  assert browser.js("!location.search && !location.hash && $('video').paused"),'Archive exit stops playback'
  browser.click('#menuOnlyLink')
  browser.playing('VTS01_VOB40_CELL01')
  assert not browser.js("$('video').muted"),'Gallery click starts playback with sound'
  browser.key('Escape',27)
  browser.wait("!menuOnly && !$('detail').open")
  browser.navigate(URL+'?view=menu#asset=VTS01_VOB49_CELL01')
  browser.playing('VTS01_VOB49_CELL01')
  browser.click('#hotspots [data-button="4"]')
  browser.playing('VTS01_VOB35_CELL01',timeout=18)
  # A browser can deny both attempts. The visible Play control must recover.
  browser.js("$('video').pause();$('video').play=()=>Promise.reject(new DOMException('Blocked for verification','NotAllowedError'));audioMuted=false;unlockSound=false;playVideo();",await_promise=True)
  assert not browser.js("$('playMenu').hidden"),'A Play control is available when autoplay cannot start'
  browser.js("delete $('video').play;true")
  browser.click('#playMenu')
  browser.playing('VTS01_VOB35_CELL01')
  assert not browser.js("$('video').muted"),'Manual Play starts with sound'
  # An older play rejection must not mute or cover the new screen.
  browser.js("$('video').play=()=>new Promise((resolve,reject)=>window.rejectOlderPlay=reject);playVideo();delete $('video').play;openAsset(byId.get('VTS01_VOB40_CELL01'));rejectOlderPlay(new DOMException('Old request','NotAllowedError'));true")
  browser.playing('VTS01_VOB40_CELL01')
  assert browser.js("!$('video').muted && $('playMenu').hidden && !unlockSound"),'Late failures leave the current playback alone'
  browser.no_errors()
  return {'muted_fallback_first_click_gallery_entry_deep_link_activation_manual_play_stale_rejection':'passed'}
 finally:browser.close()


def check_gallery(output):
 browser=BrowserCheck(output,'gallery',['--autoplay-policy=no-user-gesture-required'])
 try:
  browser.navigate(URL)
  source=(ROOT/'utilities'/'test_navigation.js').read_text(encoding='utf-8')
  result=browser.js(source+"\n(()=>{try{return testNavigation();}catch(error){return {status:'failed',message:error.message,asset:current?.id,hovered:hovered?.number,selected:menuNav.s[8]>>10,focus:{id:document.activeElement.id,button:document.activeElement.dataset.button,tag:document.activeElement.tagName},menuOnly};}})();")
  assert result['status']=='passed' and result['button_routes']==515,result
  browser.navigate(URL+'?view=menu')
  browser.playing('VTS01_VOB40_CELL01')
  assert not browser.js("$('video').muted || unlockSound"),'Audible autoplay is used when permitted'
  browser.no_errors()
  return {'status':result['status'],'button_routes':result['button_routes'],'scenarios':len(result['scenario_checks']),'audible_autoplay':'passed'}
 finally:browser.close()


def main():
 global URL
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--only',choices=['normal','restricted','gallery'])
 parser.add_argument('--url',default=URL,help='Viewer URL to check; defaults to the local index.html')
 args=parser.parse_args()
 URL=args.url
 output=pathlib.Path(tempfile.mkdtemp(prefix='stayalive-menu-check-'))
 result={'output':str(output)}
 print('Artifacts: '+str(output),flush=True)
 try:
  for name,check in [('normal',check_normal),('restricted',check_restricted),('gallery',check_gallery)]:
   if args.only and args.only!=name:continue
   result[name]=check(output)
   print(name+': '+json.dumps(result[name]),flush=True)
  result['status']='passed'
 except Exception as error:
  result['status']='failed';result['error']=str(error)
  raise
 finally:(output/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')


if __name__=='__main__':main()
