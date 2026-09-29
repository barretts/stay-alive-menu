import pathlib,json,sys,hashlib,subprocess,concurrent.futures,datetime,collections
R=pathlib.Path(sys.argv[1]);M=json.loads((R/'manifest.json').read_text(encoding='utf-8'));SRC=pathlib.Path(M['source']);errors=[]
result={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source':str(SRC),'assets':len(M['assets']),'checks':{},'media':[],'errors':errors}
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
for f in M['source_files']:
    p=R/f['file'];original=SRC/p.name
    if sha(p)!=f['sha256'] or sha(original)!=f['sha256']:errors.append('Original copy hash mismatch '+p.name)
result['checks']['original_copies_match_source']=not errors
for domain in ('VMGM','VTS01'):
    ranges=sorted((a['first_sector'],a['last_sector']) for a in M['assets'] if a['domain']==domain);expected=0
    for start,end in ranges:
        if start!=expected:errors.append(f'Gap or overlap in {domain} at sector {expected}')
        expected=end+1
    source=SRC/('VIDEO_TS.VOB' if domain=='VMGM' else 'VTS_01_0.VOB')
    if expected*2048!=source.stat().st_size:errors.append('Incomplete menu coverage '+domain)
result['checks']['complete_menu_sector_coverage']=not errors
for a in M['assets']:
    p=R/a['path'];raw=p/'original.vob'
    if sha(raw)!=a['sha256']:errors.append('Cell hash mismatch '+a['id'])
    with (SRC/('VIDEO_TS.VOB' if a['domain']=='VMGM' else f'VTS_{a["domain"][3:]}_0.VOB')).open('rb') as f:
        f.seek(a['first_sector']*2048);block=f.read(a['bytes'])
        if hashlib.sha256(block).hexdigest()!=a['sha256']:errors.append('Cell does not match source sectors '+a['id'])
    for sp in a['subpictures']:
        if sha(p/sp['file'])!=sp['sha256']:errors.append('SPU hash mismatch '+a['id']+'/'+sp['file'])
    for s in a['button_states']:
        for b in s['buttons']:
            x,y,xe,ye=b['bbox']
            if not(0<=x<=xe<720 and 0<=y<=ye<480):errors.append('Button bounds '+a['id'])
            if any(not 0<=b[k]<=s['button_count'] for k in ('up','down','left','right')):errors.append('Button direction '+a['id'])
    for g in a['graphics']:
        for f in [g['indices'],g['normal']]+[h['file'] for h in g['highlights']]:
            if not (p/f).exists():errors.append('Missing graphic '+a['id']+'/'+f)
result['checks']['original_cells_match_source']=not any('Cell' in e for e in errors);result['checks']['button_coordinates_and_directional_links_valid']=not any('Button' in e for e in errors)
def check(a):
    file=R/a['path']/'preview.mp4'
    p=subprocess.run(['ffmpeg','-v','error','-threads','2','-i',str(file),'-map','0:v:0','-map','0:a:0?','-f','null','-'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    probe=subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(R/a['path']/'original.vob')],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    source=json.loads(probe.stdout) if probe.returncode==0 else {}
    item={'asset':a['id'],'decode_exit_code':p.returncode,'decode_messages':p.stderr.decode('utf-8','replace'),'source_streams':source.get('streams',[]),'source_probe_note':'Generic MPEG duration may be wrong for DVD stills; consult IFO durations and holds.'}
    if p.returncode or p.stderr:errors.append('Preview decode issue '+a['id']+': '+item['decode_messages'][:250])
    return item
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    for item in pool.map(check,M['assets']):result['media'].append(item)
result['checks']['all_86_previews_decode_without_errors']=not any('decode' in e.lower() for e in errors)
result['checks']['all_graphics_present']=not any('graphic' in e for e in errors)
result['status']='passed' if not errors else 'failed'
(R/'validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(result['status'],result['checks'],errors,flush=True)
if errors:sys.exit(1)
