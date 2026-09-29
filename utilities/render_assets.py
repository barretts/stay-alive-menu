"""Create accessible viewing copies and decode original DVD subpicture graphics."""
import pathlib,json,sys,subprocess,concurrent.futures,math,hashlib
sys.path.insert(0,str(pathlib.Path(__file__).parent/'vendor'))
from PIL import Image,ImageDraw,ImageFont
from archive_menu import U16,palette_rgb
ROOT=pathlib.Path(sys.argv[1]); M=json.loads((ROOT/'manifest.json').read_text());PGCS={p['id']:p for p in M['pgcs']}
FONT=ImageFont.truetype(r'C:\Windows\Fonts\consola.ttf',16)
def decode_spu(b):
    at=U16(b,2);seen=set();states=[];cur={}
    while at not in seen and at+4<=len(b):
        seen.add(at);date=U16(b,at)*1024/90000;nxt=U16(b,at+2);i=at+4;commands=[]
        while i<len(b):
            op=b[i];i+=1;commands.append(op)
            if op==255:break
            if op in (0,1):cur['start']=date;cur['forced']=op==0
            elif op==2:cur['end']=date
            elif op in (3,4):
                value=U16(b,i);i+=2;cur['colors' if op==3 else 'alpha']=[value>>s&15 for s in (0,4,8,12)]
            elif op==5:
                x=int.from_bytes(b[i:i+3],'big');y=int.from_bytes(b[i+3:i+6],'big');i+=6;cur['bbox']=[x>>12,y>>12,x&4095,y&4095]
            elif op==6:cur['offsets']=[U16(b,i),U16(b,i+2)];i+=4
            else:raise ValueError(f'Unsupported SPU control {op:02x}')
        if all(k in cur for k in ('bbox','offsets','colors','alpha')):states.append(dict(cur,control_time=date,control_commands=commands))
        if nxt==at:break
        at=nxt
    if not states:raise ValueError('SPU has no bitmap definition')
    s=states[0];x,y,xe,ye=s['bbox'];w=xe-x+1;h=ye-y+1;pix=bytearray(w*h)
    for field,offset in enumerate(s['offsets']):
        nib=offset*2
        def get():
            nonlocal nib
            v=(b[nib//2]>>(4 if nib%2==0 else 0))&15;nib+=1;return v
        for row in range(field,h,2):
            col=0
            while col<w:
                code=0;t=1
                while code<t and t<=64:code=(code<<4)|get();t<<=2
                run=code>>2 if code>=4 else w-col;assert run>0 and run<=w-col,(run,w,col)
                pix[row*w+col:row*w+col+run]=bytes([code&3])*run;col+=run
            if nib%2:nib+=1
    img=Image.frombytes('L',(w,h),bytes(pix));canvas=Image.new('L',(720,480));canvas.paste(img,(x,y))
    return canvas,s,states
def rgba(indices,pal,colors,alpha):
    lut=[(*pal[colors[i]],alpha[i]*17) for i in range(4)]
    p=Image.frombytes('P',indices.size,indices.tobytes());p.putpalette([c for row in lut for c in row],'RGBA');return p.convert('RGBA')
def process(a):
    folder=ROOT/a['path'];raw=folder/'original.vob';log=[]
    saved=folder/'asset.json'
    if saved.exists() and (folder/'preview.mp4').exists():return json.loads(saved.read_text(encoding='utf-8'))
    def run(cmd):
        p=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE);log.append(p.stderr.decode('utf-8','replace'))
        if p.returncode:raise RuntimeError(a['id']+': '+log[-1][-1500:])
        return p.stdout
    # Sample original pixels before any browser conversion.
    dur=a['duration']['seconds'];seek=min(5,max(0,dur*.4))
    thumb=folder/'background.png'
    if not thumb.exists():run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(seek),'-i',str(raw),'-map','0:v:0','-frames:v','1','-vf','scale=720:480,setsar=1',str(thumb)])
    if not thumb.exists():run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(raw),'-map','0:v:0','-frames:v','1','-vf','scale=720:480,setsar=1',str(thumb)])
    p=PGCS[a['references'][0]['pgc']];pal=palette_rgb(p['palette_ycrcb']);a['palette_rgb']=[list(c) for c in pal]
    decoded=[];a['graphics']=[]
    for sp in a['subpictures']:
        indices,s,states=decode_spu((folder/sp['file']).read_bytes());stem=pathlib.Path(sp['file']).stem
        mask=stem+'_indices.png';indices.save(folder/mask)
        normal=rgba(indices,pal,s['colors'],s['alpha']);name=stem+'_normal.png';normal.save(folder/name)
        g={'source':sp['file'],'stream':sp['stream'],'start_seconds':sp['relative_seconds'],'indices':mask,'normal':name,'definition':s,'control_states':states,'highlights':[]}
        decoded.append((sp,indices,s,g));a['graphics'].append(g)
    for ni,ns in enumerate(a['button_states']):
        for button in ns['buttons']:
            group=button['group'];display=ns['display_types'][group-1]
            # IFO contains explicit wide/letterbox/pan-scan physical stream IDs.
            ctl=int(p['subpicture_controls'][0],16)
            physical=((ctl>>16)&31) if display&1 else ((ctl>>8)&31) if display&2 else (ctl&31) if display&4 else ((ctl>>24)&31)
            matching=[d for d in decoded if d[0]['stream']==0x20+physical]
            x,y,xe,ye=button['bbox'];box=(x,y,xe+1,ye+1)
            for sp,indices,s,g in matching:
                if not button['color_group']:continue
                for state,col in zip(('selected','activated'),ns['colors'][button['color_group']-1]):
                    n=int(col,16);colors=[n>>shift&15 for shift in (16,20,24,28)];alpha=[n>>shift&15 for shift in (0,4,8,12)]
                    sprite=rgba(indices,pal,colors,alpha).crop(box)
                    name=f'{pathlib.Path(sp["file"]).stem}_state{ni+1}_group{group}_button{button["number"]:02}_{state}.png';sprite.save(folder/name)
                    g['highlights'].append({'file':name,'nav_state':ni+1,'group':group,'display_type':display,'button':button['number'],'state':state,'bbox':button['bbox'],'palette_word':col})
    background=Image.open(thumb).convert('RGBA');shown=background.copy()
    # Composite any normally visible wide-format subpicture at thumbnail time.
    ctl=int(p['subpicture_controls'][0],16);wide=0x20+((ctl>>16)&31)
    candidates=[d for d in decoded if d[0]['stream']==wide and (d[0]['relative_seconds'] or 0)+d[2].get('start',0)<=seek]
    if candidates:
        sp,indices,s,g=candidates[-1];shown=Image.alpha_composite(shown,rgba(indices,pal,s['colors'],s['alpha']))
    shown.resize((854,480),Image.Resampling.LANCZOS).convert('RGB').save(folder/'preview.jpg',quality=92)
    debug=shown.copy();draw=ImageDraw.Draw(debug)
    for ns in a['button_states']:
        for b in ns['buttons']:
            if ns['display_types'][b['group']-1]&1 or (ns['groups']==1 and not ns['display_types'][0]):
                draw.rectangle(b['bbox'],outline='#00ffff',width=2);draw.text((b['bbox'][0]+3,b['bbox'][1]+2),str(b['number']),font=FONT,fill='white',stroke_width=2,stroke_fill='black')
    debug.resize((854,480),Image.Resampling.LANCZOS).convert('RGB').save(folder/'buttons.jpg',quality=92)
    video=folder/'preview.mp4'
    if not video.exists():
        run(['ffmpeg','-hide_banner','-loglevel','warning','-y','-fflags','+genpts','-i',str(raw),'-map','0:v:0','-map','0:a:0?','-sn','-dn','-vf','bwdif=mode=send_frame:parity=auto:deint=interlaced,scale=854:480:flags=lanczos,setsar=1','-c:v','libx264','-preset','fast','-crf','18','-threads','2','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-movflags','+faststart',str(video)])
    probe=json.loads(run(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(video)]));a['preview_probe']=probe;a['preview_seconds']=float(probe['format']['duration'])
    # Keep original audio uncompressed from DVD packets, plus convenient AAC.
    audio=next((s for s in probe['streams'] if s['codec_type']=='audio'),None)
    if audio:
        if not (folder/'original_audio.ac3').exists():run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(raw),'-map','0:a:0','-c:a','copy',str(folder/'original_audio.ac3')])
        if not (folder/'audio.m4a').exists():run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(video),'-map','0:a:0','-c:a','copy',str(folder/'audio.m4a')])
    a['viewing_copy']={'video':'preview.mp4','thumbnail':'preview.jpg','button_diagram':'buttons.jpg','normal_subpictures_baked_into_video':False,'note':'Original subpictures are separate PNGs with exact source timing; DVD button highlights are separate sprites.'}
    (folder/'render.log').write_text('\n'.join(log),encoding='utf-8');(folder/'asset.json').write_text(json.dumps(a,indent=2),encoding='utf-8')
    print(a['id'],f'{a["preview_seconds"]:.3f}s',len(a['graphics']),'graphics',flush=True)
    return a
if __name__=='__main__':
    # Four modest CPU encodes; the completed Topaz output is untouched.
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(process,a):a for a in M['assets']};done=[]
        for f in concurrent.futures.as_completed(futures):done.append(f.result())
    byid={a['id']:a for a in done};M['assets']=[byid[a['id']] for a in M['assets']]
    (ROOT/'manifest.json').write_text(json.dumps(M,indent=2),encoding='utf-8')
    for page,start in enumerate(range(0,len(M['assets']),24),1):
        assets=M['assets'][start:start+24];cols=4;rows=math.ceil(len(assets)/cols);sheet=Image.new('RGB',(cols*428,rows*272),(18,18,22));draw=ImageDraw.Draw(sheet)
        for i,a in enumerate(assets):
            x=(i%cols)*428;y=(i//cols)*272;img=Image.open(ROOT/a['path']/'preview.jpg').resize((424,238));sheet.paste(img,(x+2,y+2));draw.text((x+5,y+242),a['id']+f' {a["preview_seconds"]:.1f}s',font=FONT,fill='white')
        sheet.save(ROOT/f'contact-sheet-{page}.jpg',quality=93)
    print('Rendering complete',flush=True)
