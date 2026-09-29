"""Read-only DVD menu archaeology; extracts original sectors and navigation data."""
import argparse, struct, pathlib, json, hashlib, shutil, subprocess, sys, collections
sys.path.insert(0,str(pathlib.Path(__file__).parent/'vendor'))
from PIL import Image, ImageDraw, ImageFont
U16=lambda b,o:struct.unpack_from('>H',b,o)[0]
U32=lambda b,o:struct.unpack_from('>I',b,o)[0]
def dvdtime(b):
    bcd=lambda x:(x>>4)*10+(x&15)
    fps={1:25,3:30000/1001}.get(b[3]>>6,0)
    return {'seconds':round(bcd(b[0])*3600+bcd(b[1])*60+bcd(b[2])+(bcd(b[3]&63)/fps if fps else 0),6),'raw':b.hex(),'fps':fps}
def reg(r): return ('SPRM' if r&128 else 'GPRM')+str(r&127)
def command(b):
    n=int.from_bytes(b,'big'); g=lambda s,c:(n>>(s-c+1))&((1<<c)-1)
    typ=g(63,3); imm=g(60,1); op=g(51,4); cmp=g(54,3)
    dest=None
    def val(i,s,mode=1): return str(g(s,16)) if i else reg(g(s if mode==3 else s-8,8))
    def cond(v):
        if not cmp:return ''
        a,z= ('','')
        if v==1:a,z=reg(g(39,8)),val(g(55,1),31)
        if v==2:a,z=reg(g(15,8)),reg(g(7,8))
        if v==3:a,z=reg(g(43,4)),val(g(55,1),15)
        if v==4:a,z=reg(g(51,4)),val(g(55,1),31)
        if v==5:a,z=(reg(g(31,8)),reg(g(23,8))) if imm else (reg(g(39,8)),val(g(55,1),31))
        return f'if {a} {("","&","==","!=",">=",">","<=","<")[cmp]} {z}: '
    def sub():
        nonlocal dest
        k=g(7,8); names={0:'NoLink',1:'TopCell',2:'NextCell',3:'PrevCell',5:'TopProgram',6:'NextProgram',7:'PrevProgram',9:'TopPGC',10:'NextPGC',11:'PrevPGC',12:'GoUpPGC',13:'TailPGC',16:'Resume'}
        dest={'type':'LinkSub','operation':names.get(k,str(k)),'button':g(15,6)}
        return 'Link'+dest['operation']+f' (button {g(15,6)})'
    def link():
        nonlocal dest
        if op==0:return ''
        if op==1:return sub()
        names={4:('LinkPGCN',g(14,15)),5:('LinkPTT',g(9,10)),6:('LinkPGN',g(6,7)),7:('LinkCN',g(7,8))}
        if op in names:
            k,v=names[op]; dest={'type':k,'number':v}; return f'{k} {v}'
        return f'UnknownLink {op}'
    def jump():
        nonlocal dest
        if op==1:dest={'type':'Exit'}
        elif op in (2,3):dest={'type':{2:'JumpTT',3:'JumpVTS_TT'}[op],'title':g(22,7)}
        elif op==5:dest={'type':'JumpVTS_PTT','title':g(22,7),'chapter':g(41,10)}
        elif op in (6,8):
            k=g(23,2); dest={'type':'JumpSS' if op==6 else 'CallSS','domain':['FirstPlay','VMGM','VTSM','VMGM'][k]}
            if k in (1,2):dest['menu']=g(19,4)
            if k==2 and op==6:dest.update(vts=g(30,7),title=g(38,7))
            if k==3:dest['pgc']=g(46,15)
            if op==8:dest['resume_cell']=g(31,8)
        else:dest={'type':'UnknownJump','operation':op}
        return ' '.join(str(v) if k=='type' else f'{k}={v}' for k,v in dest.items())
    def setreg(v):
        sop=g(59,4); ops=['NOP','=','swap','+=','-=','*=','/=','%=','random','&=','|=','^=']
        if not sop:return 'NOP'
        r=g(35,4) if v==1 else g(51,4); s=31 if v==1 else 47
        return f'GPRM{r} {ops[sop] if sop<len(ops) else str(sop)} {val(imm,s,3 if v==3 else 1)}'
    if typ==0:
        text=cond(1)+({0:'NOP',1:f'Goto line {g(7,8)}',2:'Break',3:f'Set temporary parental level {g(11,4)}; Goto {g(7,8)}'}.get(op,f'Unknown special {op}'))
    elif typ==1:text=cond(2 if imm else 1)+(jump() if imm else link())
    elif typ==2:
        s=g(59,4)
        if s==1:
            parts=[]
            for i in (1,2,3):
                pos=47-i*8
                if g(pos,1):parts.append(f'SPRM{i}={g(pos-1,7) if imm else "GPRM"+str(g(pos-4,4))}')
            t='Set streams '+', '.join(parts)
        elif s==2:t=f'Set navigation timer {val(imm,47)}, PGC {g(30,15)}'
        elif s==3:t=f'Set GPRM{g(19,4)} {"counter" if g(23,1) else "register"} to {val(imm,47)}'
        elif s==6:t=f'Set highlighted button {g(31,16)>>10}' if imm else f'Set highlighted button from GPRM{g(19,4)}'
        else:t=f'Unknown system set {s}'
        text=cond(2)+t+('; '+link() if op else '')
    elif typ==3:text=cond(3)+setreg(1)+('; '+link() if op else '')
    elif typ==4:text=setreg(2)+'; '+cond(4)+sub()
    elif typ in (5,6):text=cond(5)+setreg(3)+'; '+sub()
    else:text=f'Unknown instruction type {typ}'
    return {'hex':b.hex(),'text':text,'destination':dest,'conditional':bool(cmp),'instruction_type':typ}
def pgc(b,o,pid,domain,srp=None):
    np,nc=b[o+2:o+4]
    p={'id':pid,'domain':domain,'programs':np,'cell_count':nc,'duration':dvdtime(b[o+4:o+8]),'next_pgc':U16(b,o+156),'previous_pgc':U16(b,o+158),'up_pgc':U16(b,o+160),'still_time':b[o+162],'playback_mode':b[o+163], 'palette_ycrcb':[f'{U32(b,o+164+4*i):08x}' for i in range(16)],'subpicture_controls':[f'{U32(b,o+28+4*i):08x}' for i in range(32)],'commands':{},'cells':[]}
    if srp:p.update(srp)
    offsets=[U16(b,o+228+i*2) for i in range(4)]
    if offsets[0]:
        co=o+offsets[0]; at=co+8
        for j,k in enumerate(('pre','post','cell')):
            num=U16(b,co+2*j); p['commands'][k]=[dict(line=i+1,**command(b[at+8*i:at+8*i+8])) for i in range(num)]; at+=8*num
    p['program_map']=list(b[o+offsets[1]:o+offsets[1]+np]) if offsets[1] else []
    for i in range(nc):
        at=o+offsets[2]+i*24; cp=o+offsets[3]+i*4
        p['cells'].append({'index':i+1,'vob_id':U16(b,cp),'cell_id':b[cp+3],'flags':b[at:at+2].hex(),'still_time':b[at+2],'cell_command':b[at+3],'duration':dvdtime(b[at+4:at+8]),'first_sector':U32(b,at+8),'last_sector':U32(b,at+20),'last_vobu_sector':U32(b,at+16)})
    return p
def pgcit(b,base,prefix,domain):
    out=[]
    for i in range(U16(b,base)):
        at=base+8+i*8; entry=b[at]
        out.append(pgc(b,base+U32(b,at+4),prefix+str(i+1),domain,{'number':i+1,'entry_id':entry,'entry_menu':(entry&15) if entry&128 else None,'parental_mask':U16(b,at+2)}))
    return out
def menus(b,sector,domain):
    if not sector:return []
    base=sector*2048; out=[]
    for i in range(U16(b,base)):
        at=base+8+i*8; lang=b[at:at+2].decode('ascii',errors='replace')
        for p in pgcit(b,base+U32(b,at+4),f'{domain}_LU{i+1}_PGC',domain):p.update(language=lang,language_unit=i+1);out.append(p)
    return out
def palette_rgb(p):
    result=[]
    for v in p:
        n=int(v,16); y=(n>>16)&255; cr=((n>>8)&255)-128; cb=(n&255)-128
        yy=1.164383*(y-16)
        result.append(tuple(max(0,min(255,round(c))) for c in (yy+1.596027*cr,yy-.391762*cb-.812968*cr,yy+2.017232*cb)))
    return result
def nav(pci):
    if len(pci)<979:return None
    o=96; ss=U16(pci,o); flags=U16(pci,o+14); groups=(flags>>12)&3; count=pci[o+17]
    if not ss&3 or not groups or not count:return None
    colors=[[f'{U32(pci,o+22+i*8+j*4):08x}' for j in range(2)] for i in range(3)]
    out={'status':ss,'start_ptm':U32(pci,o+2),'end_ptm':U32(pci,o+6),'selection_end_ptm':U32(pci,o+10),'groups':groups,'display_types':[(flags>>s)&7 for s in (8,4,0)],'button_count':count,'button_offset':pci[o+16],'forced_select':pci[o+20],'forced_activate':pci[o+21],'colors':colors,'buttons':[]}
    for group in range(groups):
        for i in range(count):
            off=o+46+(group*(36//groups)+i)*18; d=pci[off:off+18]; a=int.from_bytes(d[:3],'big'); b=int.from_bytes(d[3:6],'big')
            out['buttons'].append({'group':group+1,'number':i+1,'color_group':a>>22,'bbox':[a>>12&1023,b>>12&1023,a&1023,b&1023],'auto_action':b>>22,'up':d[6]&63,'down':d[7]&63,'left':d[8]&63,'right':d[9]&63,'command':command(d[10:18])})
    return out
def parse_pes(data):
    at=0
    while True:
        at=data.find(b'\0\0\1',at)
        if at<0 or at+6>len(data):break
        sid=data[at+3]
        if sid in (0xbf,0xbd):
            size=U16(data,at+4); payload=data[at+6:at+6+size]
            pts=None
            if sid==0xbd and len(payload)>=3:
                if payload[1]&128 and len(payload)>=8:
                    q=payload[3:8];pts=((q[0]>>1&7)<<30)|(q[1]<<22)|((q[2]>>1)<<15)|(q[3]<<7)|(q[4]>>1)
                payload=payload[3+payload[2]:]
            if payload:yield sid,payload,pts
            at+=6+size
        else:at+=4
def scan_asset(path):
    navs=[]; spool=collections.defaultdict(bytearray); packets=[]; last_spu={};first_video_ptm=None
    with path.open('rb') as f:
        sector=0
        while chunk:=f.read(2048):
            pci=None; dsi=None
            for sid,p,pts in parse_pes(chunk):
                if sid==0xbf and p[0]==0:pci=p[1:]
                if sid==0xbf and p[0]==1:dsi=p[1:]
                if sid==0xbd and 0x20<=p[0]<=0x3f:
                    stream=p[0]
                    if not spool[stream]:last_spu[stream]=(sector,pts)
                    spool[stream]+=p[1:]
                    while len(spool[stream])>=2 and len(spool[stream])>=U16(spool[stream],0):
                        n=U16(spool[stream],0)
                        if n<4:break
                        ss,pt=last_spu[stream];packets.append((stream,ss,pt,bytes(spool[stream][:n]))); del spool[stream][:n]
            if pci is not None and dsi is not None:
                if first_video_ptm is None:first_video_ptm=U32(pci,12)
                h=nav(pci)
                if h:
                    h.update(sector=sector,vob_id=U16(dsi,24),cell_id=dsi[27],cell_elapsed=dvdtime(dsi[28:32]),video_start_ptm=U32(pci,12))
                    navs.append(h)
            sector+=1
    # Keep every distinct button definition/color state, with occurrence range.
    unique={}
    for h in navs:
        key=json.dumps({k:v for k,v in h.items() if k not in ('sector','start_ptm','end_ptm','selection_end_ptm','video_start_ptm','cell_elapsed','status')},sort_keys=True)
        if key not in unique:unique[key]=dict(h,last_sector=h['sector'],occurrences=1)
        else:unique[key]['last_sector']=h['sector'];unique[key]['occurrences']+=1
    return list(unique.values()),packets,len(navs),first_video_ptm
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',required=True);ap.add_argument('--out',required=True);ap.add_argument('--inventory-only',action='store_true');args=ap.parse_args()
    src=pathlib.Path(args.source);out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=True)
    m={'source':str(src),'edition':'Stay Alive NTSC DVD9','coordinate_space':{'width':720,'height':480,'display_aspect':'16:9','preview_size':[854,480]},'pgcs':[],'titles':[],'assets':[],'source_files':[]}
    for f in sorted(src.glob('*.IFO')):
        b=f.read_bytes();dom='VMGM' if f.name=='VIDEO_TS.IFO' else 'VTS'+f.name[4:6]
        if dom=='VMGM':
            m['pgcs']+=menus(b,U32(b,0xc8),dom)
            fp=U32(b,0x84)
            if fp:m['first_play']=pgc(b,fp,'FirstPlay','FirstPlay')
            tt=U32(b,0xc4)*2048
            for i in range(U16(b,tt)):
                o=tt+8+12*i;m['titles'].append({'title':i+1,'angles':b[o+1],'chapters':U16(b,o+2),'vts':b[o+6],'vts_title':b[o+7]})
        else:
            m['pgcs']+=menus(b,U32(b,0xd0),dom)
            if U32(b,0xcc):m.setdefault('title_pgcs',[]).extend(pgcit(b,U32(b,0xcc)*2048,dom+'_TITLE_PGC',dom+'_TITLE'))
            if U32(b,0xc8):
                tt=U32(b,0xc8)*2048;num=U16(b,tt);last=U32(b,tt+4)+1
                chapters=[]
                for i in range(num):
                    start=U32(b,tt+8+i*4);end=U32(b,tt+12+i*4) if i+1<num else last
                    chapters.append([{'pgc':U16(b,tt+j),'program':U16(b,tt+j+2)} for j in range(start,end,4)])
                m.setdefault('title_chapter_tables',{})[dom]=chapters
    print('PGCs',len(m['pgcs']),'with cells',sum(bool(p['cells']) for p in m['pgcs']),flush=True)
    if args.inventory_only:
        (out/'inventory.json').write_text(json.dumps(m,indent=2));return
    original=out/'original';original.mkdir(exist_ok=True)
    for f in sorted(src.iterdir()):
        if f.suffix in ('.IFO','.BUP') or f.name=='VIDEO_TS.VOB' or f.name.endswith('_0.VOB'):
            to=original/f.name
            if not to.exists() or to.stat().st_size!=f.stat().st_size:shutil.copy2(f,to)
            m['source_files'].append({'file':f'original/{f.name}','bytes':to.stat().st_size,'sha256':hashlib.file_digest(to.open('rb'),'sha256').hexdigest()})
    cells={}
    for p in m['pgcs']:
        for c in p['cells']:
            k=(p['domain'],c['first_sector'],c['last_sector'])
            if k not in cells:cells[k]={'id':f'{p["domain"]}_VOB{c["vob_id"]:02}_CELL{c["cell_id"]:02}','domain':p['domain'],'vob_id':c['vob_id'],'cell_id':c['cell_id'],'first_sector':c['first_sector'],'last_sector':c['last_sector'],'duration':c['duration'],'references':[]}
            cells[k]['references'].append({'pgc':p['id'],'cell_index':c['index'],'still_time':c['still_time']});c['asset']=cells[k]['id']
    for a in cells.values():
        dest=out/'assets'/a['id'];dest.mkdir(parents=True,exist_ok=True)
        file=src/('VIDEO_TS.VOB' if a['domain']=='VMGM' else f'VTS_{a["domain"][3:]}_0.VOB')
        raw=dest/'original.vob';size=(a['last_sector']-a['first_sector']+1)*2048
        if not raw.exists() or raw.stat().st_size!=size:
            with file.open('rb') as f,raw.open('wb') as w:
                f.seek(a['first_sector']*2048);left=size
                while left:
                    block=f.read(min(left,4*1024*1024));assert block;w.write(block);left-=len(block)
        states,spus,count,first_ptm=scan_asset(raw);a.update(path=f'assets/{a["id"]}',bytes=size,button_states=states,nav_with_buttons=count,first_video_ptm=first_ptm,subpictures=[])
        for i,(stream,sector,pts,data) in enumerate(spus):
            name=f'subpicture_{stream:02x}_{i+1:03}.spu';(dest/name).write_bytes(data)
            a['subpictures'].append({'file':name,'stream':stream,'sector':sector,'pts':pts,'relative_seconds':round((pts-first_ptm)/90000,6) if pts is not None and first_ptm is not None else None,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
        a['sha256']=hashlib.file_digest(raw.open('rb'),'sha256').hexdigest();m['assets'].append(a)
        print(a['id'],'seconds',a['duration']['seconds'],'states',len(states),'SPUs',len(spus),flush=True)
    (out/'manifest.json').write_text(json.dumps(m,indent=2),encoding='utf-8')
    print('Saved manifest',out,flush=True)
if __name__=='__main__':main()
