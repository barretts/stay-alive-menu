import json,pathlib,sys,csv,html,math,datetime,collections,shutil
R=pathlib.Path(sys.argv[1])
def write_page():
    template=pathlib.Path(__file__).with_name('catalog-template.html').read_text(encoding='utf-8')
    archive=json.loads((R/'manifest.json').read_text(encoding='utf-8'))
    (R/'index.html').write_text(template.replace('__ARCHIVE_DATA__',json.dumps(archive).replace('<','\\u003c')),encoding='utf-8')

# UI-only rebuilds do not need Pillow or rewrite the extracted archive.
if '--page-only' in sys.argv[2:]:
    write_page()
    print('Rebuilt index.html',flush=True)
    sys.exit(0)
sys.path.insert(0,str(pathlib.Path(__file__).parent/'vendor'))
from PIL import Image,ImageDraw,ImageFont
M=json.loads((R/'manifest.json').read_text(encoding='utf-8'));P={p['id']:p for p in M['pgcs']};A={a['id']:a for a in M['assets']}
PGC_NAMES={1:'Activated main menu',2:'Set up',3:'Audio/register dispatcher',4:'Captions & subtitles',5:'Scene selection / character style',6:'Scene selection / television style',7:'Bonus features',8:'Audio commentary',9:'Commentary/play dispatcher',10:'Register your DVD',11:'Bonus exit transition',12:'Activated main dispatcher',13:'Character builder / character 1 (Hutch)',14:'Failed activation / random outcomes',15:'Instructions / The Prayer of Elizabeth',16:'Character builder / character 2 (Abigail)',17:'Character builder / character 3'}
MAIN_BUTTONS=['Character','Shirt','Weapon','Activate','Instructions','Play','Scene selection','Bonus features','Set up']
def identity(a):
    v=a['vob_id'];dom=a['domain']
    if dom=='VMGM':return ('Startup and stills',f'VMG still/dispatcher {v}')
    if v in [40]+list(range(43,78)):
        character=1 if v<=53 else 2 if v<=65 else 3
        variant=([40]+list(range(43,54))).index(v)+1 if character==1 else v-(53 if character==2 else 65)
        a['character']=character;a['variant']=variant;a['correct_activation']=v in (49,64,69)
        return ('Character builder',f'Character {character} · combination {variant:02}'+(' · correct activation' if a['correct_activation'] else ''))
    if 1<=v<=5:return ('Scene selection',f'Scene selection · chapters {1+(v-1)*4}–{v*4} · character style')
    if 13<=v<=17:return ('Scene selection',f'Scene selection · chapters {1+(v-13)*4}–{(v-12)*4} · television style')
    if 26<=v<=31:return ('Activation outcomes',f'Failed activation outcome {v-25}')
    if v in (33,35,37):return ('Activated main menus',f'Television main menu · variation {(v-31)//2}')
    if v in (32,34,36):return ('Transitions',f'Television main entrance · variation {(v-30)//2}')
    if v in (12,23):return ('Set up','Set up · '+('character style' if v==12 else 'television style'))
    if v in (9,24):return ('Captions & subtitles','Captions & subtitles · '+('character style' if v==9 else 'television style'))
    if v in (8,19):return ('Bonus features','Bonus features · '+('character style' if v==8 else 'television style'))
    if v in (10,25):return ('Audio commentary','Audio commentary · '+('character style' if v==10 else 'television style'))
    if v in (11,22):return ('DVD registration','Register your DVD · '+('character style' if v==11 else 'television style'))
    if v==42:return ('Instructions','Instructions · The Prayer of Elizabeth')
    return ('Transitions',{6:'Bonus entrance · static/glitch',18:'Bonus entrance · cursor',7:'Bonus exit · static/glitch',21:'Bonus exit · cursor',38:'Menu opening · entrance',39:'Menu opening · character fade-in',20:'Commentary dispatcher still',41:'Commentary dispatcher still'}.get(v,f'Transition/still {v}'))
def label(a,b):
    v=a['vob_id'];n=b['number']
    if a['category']=='Character builder':return MAIN_BUTTONS[n-1] if n<=9 else str(n)
    if v in (33,35,37):return ['Play','Scene selection','Bonus features','Set up','Character selection'][n-1]
    if v in (12,23):return ['Captions & subtitles','Register your DVD','Return to film','Main menu'][n-1]
    if v in (9,24):return ['English for the hearing impaired','French','Spanish','None','Set up'][n-1]
    if v in (8,19):return (['Visual effects reel','Audio commentary','Main menu'] if v==8 else ['Visual effects reel','Audio commentary','Character selection','Main menu'])[n-1]
    if v in (10,25):return ['Commentary on','Commentary off','Bonus features'][n-1]
    if v in (11,22):return 'Set up'
    if v==42:return 'Main menu'
    if a['category']=='Scene selection':
        page=v-1 if v<=5 else v-13
        if n<=4:return f'Chapter {page*4+n}'
        if n<=9:return f'Chapters {(n-5)*4+1}–{(n-4)*4}'
        return 'Main menu' if n==10 else 'Previous page' if n in (11,12) else 'Next page'
    if a['domain']=='VMGM' and v==6:return 'Continue' if n==1 else 'Alternative parental branch'
    return f'Button {n}'
def context_target(p,d):
    if not d:return []
    typ=d['type'];dom=p['domain'];lu=p.get('language_unit',1)
    if typ=='LinkPGCN':return [f'{dom}_LU{lu}_PGC{d["number"]}']
    if typ in ('LinkPGN','LinkCN'):
        num=d['number'];cell=p['program_map'][num-1] if typ=='LinkPGN' and 0<num<=len(p['program_map']) else num if typ=='LinkCN' else None
        return [p['cells'][cell-1]['asset']] if cell and 0<cell<=len(p['cells']) else [p['id']+f':{typ}{num}']
    if typ in ('JumpSS','CallSS'):
        domain=d['domain'];domain=f'VTS{d.get("vts",int(dom[3:]) if dom.startswith("VTS") else 1):02}' if domain=='VTSM' else domain
        if domain=='FirstPlay':return ['FirstPlay']
        if 'pgc' in d:return [f'{domain}_LU1_PGC{d["pgc"]}']
        return [q['id'] for q in M['pgcs'] if q['domain']==domain and q.get('entry_menu')==d.get('menu')]
    if typ=='JumpTT':return [f'Title{d["title"]}']
    if typ in ('JumpVTS_TT','JumpVTS_PTT'):
        vts=int(dom[3:]) if dom.startswith('VTS') else None
        return [f'Title{q["title"]}'+(f':Chapter{d["chapter"]}' if 'chapter' in d else '') for q in M['titles'] if q['vts']==vts and q['vts_title']==d['title']]
    if typ=='LinkSub':return [p['id']+':'+d['operation']]
    return [typ]
for a in M['assets']:
    a['category'],a['label']=identity(a)
    for ns in a['button_states']:
        for b in ns['buttons']:b['label']=label(a,b)
for p in M['pgcs']:
    p['label']=PGC_NAMES.get(p['number'],p['id']) if p['domain']=='VTS01' else p['id']
edges=[]
for p in M['pgcs']+([M['first_play']] if 'first_play' in M else []):
    for phase,cs in p['commands'].items():
        for c in cs:
            edges.append({'from':p['id'],'trigger':phase,'line':c['line'],'command':c['text'],'raw':c['hex'],'conditional':c['conditional'],'targets':context_target(p,c['destination'])})
    for c in p['cells']:
        edges.append({'from':p['id'],'trigger':'cell asset','cell':c['index'],'targets':[c['asset']]})
for a in M['assets']:
    for ref in a['references']:
        p=P[ref['pgc']]
        for si,ns in enumerate(a['button_states']):
            for b in ns['buttons']:
                edges.append({'from':a['id'],'context_pgc':p['id'],'trigger':'button','nav_state':si+1,'group':b['group'],'button':b['number'],'label':b['label'],'bbox':b['bbox'],'command':b['command']['text'],'raw':b['command']['hex'],'targets':context_target(p,b['command']['destination'])})
        cell=p['cells'][ref['cell_index']-1];cn=cell['cell_command']
        if cn:
            cmd=p['commands'].get('cell',[])[cn-1];a.setdefault('end_actions',[]).append({'context_pgc':p['id'],'cell_command':cmd['text'],'targets':context_target(p,cmd['destination'])})
        if cell['still_time']:a.setdefault('holds',[]).append({'context_pgc':p['id'],'seconds':cell['still_time'] if cell['still_time']!=255 else 'indefinite'})
chapters=[]
for t in M['titles']:
    domain=f'VTS{t["vts"]:02}';pts=M['title_chapter_tables'][domain][t['vts_title']-1]
    for i,c in enumerate(pts):
        tp=next(p for p in M['title_pgcs'] if p['id']==f'{domain}_TITLE_PGC{c["pgc"]}')
        ci=tp['program_map'][c['program']-1];time=sum(x['duration']['seconds'] for x in tp['cells'][:ci-1])
        chapters.append({'title':t['title'],'chapter':i+1,'pgc':tp['id'],'program':c['program'],'approximate_ifo_start_seconds':round(time,3)})
M['navigation_edges']=edges;M['chapter_destinations']=chapters;M['archive_notes']=['Original VIDEO_TS/VTS menu VOBs, IFOs and BUPs are copied unchanged. All 86 unique menu sector ranges are retained.', 'The gallery follows the extracted menu commands for screen navigation, customization, activation, and stream selections. Full movie playback and DVD resume behavior are external destinations; raw conditional commands remain in the map.', 'Some menu cells are a single still frame held by DVD navigation. Their MP4 video track can be shorter than the IFO hold or audio.', 'Browser previews retain the background video/audio. Original normal subpictures and selected/activated button graphics are separate PNG assets, with PTS timing.', 'Movie, trailers, and visual-effects title bodies are external navigation targets; this menu archive does not duplicate them.', 'Preview size is 854×480 square pixels; original video and button coordinates are 720×480 anamorphic. Pan-and-scan button groups are separately retained.']
stats={'unique_assets':len(M['assets']),'menu_pgcs':len(M['pgcs']),'interactive_assets':sum(bool(a['button_states']) for a in M['assets']),'character_combinations':sum(a['category']=='Character builder' for a in M['assets']),'subpicture_packets':sum(len(a['subpictures']) for a in M['assets']),'highlight_pngs':sum(len(g['highlights']) for a in M['assets'] for g in a['graphics']),'navigation_edges':len(edges)}
M['interactive_gallery']={'navigation_script':'menu-navigation.js','hotspots':True,'keyboard_navigation':True,'browser_history':True,'direct_asset_links':True,'external_video_titles':True};M['statistics']=stats;(R/'manifest.json').write_text(json.dumps(M,indent=2),encoding='utf-8');(R/'navigation-map.json').write_text(json.dumps({'pgcs':M['pgcs'],'titles':M['titles'],'chapters':chapters,'edges':edges},indent=2),encoding='utf-8')
with (R/'assets.csv').open('w',newline='',encoding='utf-8-sig') as f:
    writer=csv.DictWriter(f,fieldnames=['id','label','category','path','ifo_seconds','preview_seconds','buttons_wide','original_bytes','correct_activation']);writer.writeheader()
    for a in M['assets']:writer.writerow({'id':a['id'],'label':a['label'],'category':a['category'],'path':a['path'],'ifo_seconds':a['duration']['seconds'],'preview_seconds':a['preview_seconds'],'buttons_wide':a['button_states'][0]['button_count'] if a['button_states'] else 0,'original_bytes':a['bytes'],'correct_activation':a.get('correct_activation','')})
with (R/'buttons.csv').open('w',newline='',encoding='utf-8-sig') as f:
    fields=['asset','context','state','group','button','label','x1','y1','x2','y2','up','down','left','right','command','targets'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
    for a in M['assets']:
        for ref in a['references']:
            for si,s in enumerate(a['button_states']):
                for b in s['buttons']:
                    w.writerow(dict(asset=a['id'],context=ref['pgc'],state=si+1,group=b['group'],button=b['number'],label=b['label'],x1=b['bbox'][0],y1=b['bbox'][1],x2=b['bbox'][2],y2=b['bbox'][3],up=b['up'],down=b['down'],left=b['left'],right=b['right'],command=b['command']['text'],targets=' | '.join(context_target(P[ref['pgc']],b['command']['destination']))))
readme=f'''# Stay Alive — original NTSC DVD menu archive

Open **index.html** for the local asset gallery. Open **Menu-Map.md** for the navigation summary. No server or internet connection is needed.

{stats['unique_assets']} unique menu assets; {stats['menu_pgcs']} menu program chains; {stats['interactive_assets']} assets with buttons; {stats['character_combinations']} character combinations; {stats['subpicture_packets']} original subpicture packets; {stats['highlight_pngs']} selected/activated highlight PNGs.

## Contents

- `original/`: unchanged original IFO, BUP, and menu VOB files.
- `assets/`: one directory per unique physical cell, with original VOB sectors, playable MP4, original AC3 and AAC audio where present, thumbnails, button diagrams, original SPU packets, indexed masks, normal overlays, and selected/activated button sprites.
- `manifest.json`: complete machine-readable inventory, palettes, timings, DVD registers/commands, button boxes, and asset references.
- `navigation-map.json`, `buttons.csv`, `assets.csv`: navigation and spreadsheet inventories.
- `contact-sheet-*.jpg`: visual inventory.
- `validation.json`: verification results.
- `utilities/`: reproducible extraction scripts and requirements.

## Git contents

The Git checkout includes the working gallery and menu-only view, playback MP4s, thumbnails, normal/highlight overlays, button diagrams, navigation data, contact sheets, and utilities. `.gitignore` excludes original DVD files, raw extracted VOB/audio/subpicture packets, duplicate AAC files, rendering intermediates, per-asset caches, and logs. Those files remain in the local archive; excluding them from Git does not delete them.

A fresh checkout can play and navigate the menus. Original VOB download links and full source validation require the excluded local files. Re-extraction and re-encoding require the original DVD source described below.

## GitHub Pages

In the repository's **Settings → Pages**, choose **GitHub Actions** as the source, then run **Publish GitHub Pages** from the Actions tab. The site is at `https://barretts.github.io/stay-alive-menu/`; append `?view=menu` for the autoplay menu view.

The Pages workflow publishes on pushes to `main` or a manual run after GitHub Pages is enabled with GitHub Actions as its source. `utilities/build_site.py` assembles only the viewer, playable media, overlays, and linked archive documents in `_site/`. Originals, extraction caches, and utilities are not published. The hosted viewer hides links to local-only movie and original VOB files; movie/bonus selections explain that those videos are not included and offer a return to the menu.

## Interpretation and timing

'''+''.join('- '+n+'\n' for n in M['archive_notes'])+'''
Choose **Explore the DVD menu**, or open any asset. Click the original menu hotspots or sidebar buttons to move between screens. Arrow keys follow the DVD directional links; Enter selects. Character, shirt, weapon, activation, setup, and return routes keep the current menu state. Browser Back and Forward restore the previous screen and selection. Each screen has an `#asset=...` link. Original transitions advance automatically and can be skipped. Short black dispatcher holds are skipped. Movie, commentary, chapter, and bonus-video destinations show a link to the separate video file. These menu choices do not change the existing movie export. The three successful activation combinations are identified in the map from their actual Activate commands.

Choose **Menu-only view**, or open `index.html?view=menu`, for a viewport-fitted menu with automatic video and sound, original hotspots, and keyboard navigation. Small sound and Archive controls appear on movement or keyboard focus. If the browser blocks audible autoplay, video starts muted and sound enables on the first click or menu selection; an explicit mute stays muted across screens. Browser history and `#asset=...` links work in both views.

The source rip is `G:\\_new\\STAY_ALIVE\\VIDEO_TS`. The movie upscale remains separate in `D:\\StayAlive`.
'''
(R/'README.md').write_text(readme,encoding='utf-8')
md=['# Stay Alive DVD menu map','', 'The menu contains a character-building puzzle and two visual styles. This map is derived from the original IFO and NAV commands; all raw commands remain in the manifest.','', '## Main routes','', '| Screen/action | Destination or behavior |','|---|---|','| Character / Shirt / Weapon | Changes among 36 authored clips: three characters with 12 combinations each. |','| Activate, correct combination | PGC post commands set the activated character and enter one of three television-style main menus. |','| Activate, incorrect combination | One of six randomly chosen outcome clips, then returns to the builder. |','| Instructions | The Prayer of Elizabeth; returns to the builder. |','| Play | Movie/resume dispatcher, preserving DVD audio and resume state. |','| Scene selection | Five pages, chapters 1–20, in character and television styles. Chapter 21 is also present in the movie chapter table. |','| Bonus features | Visual effects reel, audio commentary, main-menu return; activated style also offers Character selection. |','| Set up | Captions & subtitles, DVD registration, return to film, main menu. |','| Captions & subtitles | English hearing-impaired, French, Spanish, None. |','| Audio commentary | On/off, then movie or bonus menu. |','', '## Successful activation combinations','', 'These are the only three builder clips whose Activate command executes `LinkTailPGC`; the other 33 execute `LinkPGCN 14`. The labels describe source clips rather than guessing clothing names.','']
for vid in (49,64,69):
    a=A[f'VTS01_VOB{vid:02}_CELL01'];md.append(f'- [{a["label"]}]({a["path"]}/preview.mp4) · [still]({a["path"]}/preview.jpg)')
md+=['','## Program chains','', '| PGC | Role | Cell assets |','|---|---|---|']
for p in M['pgcs']:md.append(f'| {p["id"]} | {p["label"]} | '+', '.join(f'[{c["asset"]}]({A[c["asset"]]["path"]}/preview.mp4)' for c in p['cells'])+' |')
md+=['','## Loops, transitions, and player state','','Most playable menus use a cell command `LinkTopProgram` to loop their current program. The builder uses GPRM9 for the selected combination, GPRM10 for activation/character state, and GPRM4 for entrance-versus-loop routing. PGC14 chooses a failed outcome using `random 6`. The complete pre/post/cell command order, conditions, button directional links, and palettes are in `navigation-map.json`.','','Some command-only PGCs and still cells are dispatchers. Their presence does not mean a separate visible menu exists. First-play enters the VMG startup branch; startup title bodies and the visual-effects reel remain title targets on the source rip.','','## DVD title destinations','','| Title | VTS / title | Chapters |','|---|---|---|']
for t in M['titles']:md.append(f'| {t["title"]} | {t["vts"]} / {t["vts_title"]} | {t["chapters"]} |')
md+=['','## Limits','','The gallery now follows the menu command subset used by the extracted screens. All 515 widescreen button routes were checked, including customization, activation, setup, scene-page navigation, and returns. Full video-title playback and DVD player resume behavior use separate external destinations. Short black dispatcher holds are skipped in the browser. Raw conditional commands remain available for further reconstruction. The archive includes all original menu subtitle packets and decoded highlights for both wide and pan-and-scan button groups.','']
(R/'Menu-Map.md').write_text('\n'.join(md),encoding='utf-8')
font=ImageFont.truetype(r'C:\Windows\Fonts\consola.ttf',15)
for page,start in enumerate(range(0,len(M['assets']),24),1):
    sub=M['assets'][start:start+24];im=Image.new('RGB',(1712,math.ceil(len(sub)/4)*288),(18,18,22));draw=ImageDraw.Draw(im)
    for i,a in enumerate(sub):
        x=i%4*428;y=i//4*288;im.paste(Image.open(R/a['path']/'preview.jpg').resize((424,238)),(x+2,y+2));draw.text((x+5,y+242),a['id'],font=font,fill='white');draw.text((x+5,y+260),a['label'][:43],font=font,fill='#b7c5d2')
    im.save(R/f'contact-sheet-{page}.jpg',quality=93)
shutil.copy2(pathlib.Path(__file__).with_name('menu-navigation.js'),R/'menu-navigation.js')
write_page()
print(json.dumps(stats),flush=True)
