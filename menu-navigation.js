/* Navigation for the command subset used by this DVD's extracted menus. */
'use strict';
class MenuNavigation {
  constructor(archive, random=Math.random) {
    this.archive=archive;this.random=random;
    this.assets=new Map(archive.assets.map(a=>[a.id,a]));
    this.pgcs=new Map(archive.pgcs.map(p=>[p.id,p]));
    this.reset();
  }
  reset(){this.g=Array(16).fill(0);this.s=Array(24).fill(0);this.g[9]=101;this.g[14]=1;this.s[13]=15;this.pgc=null;this.cell=1;this.asset=null;this.steps=0;}
  snapshot(){return {g:[...this.g],s:[...this.s],pgc:this.pgc,cell:this.cell,asset:this.asset};}
  restore(state){this.g=[...state.g];this.s=[...state.s];this.pgc=state.pgc;this.cell=state.cell;this.asset=state.asset;this.steps=0;}
  seed(assetId){
    const a=this.assets.get(assetId);if(!a)throw Error('Unknown menu screen');
    const ref=a.references[0];this.pgc=ref.pgc;this.cell=ref.cell_index;this.asset=a.id;
    this.g[4]=0;this.g[5]=0;this.g[7]=0;this.g[14]=1;
    if(a.character){this.g[9]=a.character*100+a.variant;this.g[10]=0;}
    else if(a.category==='Activated main menus'){
      const character={33:2,35:1,37:3}[a.vob_id];this.g[9]=character;this.g[10]=character;
    }else if(a.label.includes('television style')){this.g[9]=1;this.g[10]=1;}
    else if(['Set up','Captions & subtitles','Bonus features','Audio commentary','DVD registration','Scene selection','Instructions'].includes(a.category)){
      if(this.g[9]<100)this.g[9]=101;this.g[10]=0;
    }
    return {kind:'asset',assetId:a.id,pgcId:this.pgc,cellIndex:this.cell};
  }
  start(){this.reset();return this.seed('VTS01_VOB40_CELL01');}
  tick(){if(++this.steps>160)throw Error('This navigation branch could not be resolved.');}
  value(token){const m=/^(GPRM|SPRM)(\d+)$/.exec(token);return m?(m[1]==='GPRM'?this.g:this.s)[Number(m[2])]:Number(token);}
  condition(a,op,b){const x=this.value(a),y=this.value(b);return {'==':x===y,'!=':x!==y,'>=':x>=y,'>':x>y,'<=':x<=y,'<':x<y,'&':Boolean(x&y)}[op];}
  instruction(c){
    this.tick();let text=c.text;
    const guard=/^if ((?:GPRM|SPRM)\d+) (==|!=|>=|>|<=|<|&) ((?:GPRM|SPRM)\d+|\d+): (.*)$/.exec(text);
    if(guard){if(!this.condition(guard[1],guard[2],guard[3]))return null;text=guard[4];}
    const first=text.split(';')[0].trim();let m;
    if((m=/^Goto line (\d+)$/.exec(first)))return {goto:Number(m[1])};
    if(first==='Break')return {break:true};
    if((m=/^Set temporary parental level (\d+); Goto (\d+)$/.exec(text))){this.s[13]=Number(m[1]);return {goto:Number(m[2])};}
    if((m=/^GPRM(\d+) (=|swap|\+=|-=|\*=|\/=|%=|random|&=|\|=|\^=) ((?:GPRM|SPRM)\d+|\d+)$/.exec(first))){
      const r=Number(m[1]),v=this.value(m[3]),old=this.g[r];let n;
      switch(m[2]){
        case '=':n=v;break;case '+=':n=old+v;break;case '-=':n=old-v;break;case '*=':n=old*v;break;
        case '/=':n=v?Math.floor(old/v):65535;break;case '%=':n=v?old%v:65535;break;
        case 'random':n=v?1+Math.floor(this.random()*v):1;break;case '&=':n=old&v;break;case '|=':n=old|v;break;case '^=':n=old^v;break;
        case 'swap':n=v;if(m[3].startsWith('GPRM'))this.g[Number(m[3].slice(4))]=old;break;
      }this.g[r]=Math.min(65535,Math.max(0,n));
    }else if((m=/^Set highlighted button (\d+)$/.exec(first)))this.s[8]=Number(m[1])*1024;
    else if((m=/^Set highlighted button from GPRM(\d+)$/.exec(first)))this.s[8]=this.g[Number(m[1])];
    else if(first.startsWith('Set streams ')){
      for(const m of first.matchAll(/SPRM(\d+)=((?:GPRM|SPRM)\d+|\d+)/g))this.s[Number(m[1])]=this.value(m[2]);
    }else if((m=/^Set GPRM(\d+) (?:counter|register) to ((?:GPRM|SPRM)\d+|\d+)$/.exec(first)))this.g[Number(m[1])]=this.value(m[2]);
    else if(!c.destination&&!/^(NOP|Nop)$/.test(first))throw Error('Unsupported navigation command: '+text);
    return c.destination?{destination:c.destination}:null;
  }
  list(commands){
    for(let i=0;i<commands.length;){const result=this.instruction(commands[i]);
      if(result?.goto){i=result.goto-1;continue;}if(result?.break)return null;
      if(result?.destination)return this.route(result.destination);i++;
    }return null;
  }
  enter(pgcId){
    this.tick();const p=this.pgcs.get(pgcId);if(!p)throw Error('Menu destination is unavailable: '+pgcId);
    this.pgc=p.id;this.cell=1;
    const pre=this.list(p.commands.pre||[]);if(pre)return pre;
    // These short black cells only dispatch movie/audio navigation; skip their holds in the browser.
    if(['VTS01_LU1_PGC9','VMGM_LU1_PGC9','VMGM_LU1_PGC12'].includes(p.id))return this.post();
    return p.cells.length?this.showCell(1):this.post();
  }
  post(){const p=this.pgcs.get(this.pgc);return this.list(p.commands.post||[])||{kind:'notice',message:'This branch has no further menu screen.'};}
  showCell(number){
    this.tick();const p=this.pgcs.get(this.pgc),cell=p.cells[number-1];
    // Command-only dispatchers on this disc contain links to placeholder programs.
    if(!cell)return this.post();
    this.cell=number;this.asset=cell.asset;
    return {kind:'asset',assetId:cell.asset,pgcId:p.id,cellIndex:number};
  }
  programNumber(){const p=this.pgcs.get(this.pgc);let n=1;for(let i=0;i<p.program_map.length;i++)if(p.program_map[i]<=this.cell)n=i+1;return n;}
  program(number){const p=this.pgcs.get(this.pgc);return p.program_map[number-1]?this.showCell(p.program_map[number-1]):this.post();}
  title(number,chapter=1){
    const title=this.archive.titles.find(t=>t.title===number);if(!title)throw Error('Unknown DVD title');
    const pgc=this.archive.title_pgcs.find(p=>p.id===`VTS${String(title.vts).padStart(2,'0')}_TITLE_PGC1`);
    // Title 2 is the menu-entry dispatcher, not a video title.
    if(number===2){const p=this.archive.title_pgcs.find(p=>p.id==='VTS01_TITLE_PGC2');return this.list(p.commands.pre);}
    return {kind:'title',title:number,chapter,vts:title.vts,vtsTitle:title.vts_title,name:{1:'Stay Alive — movie',3:'DVD startup notice',4:'DVD previews',5:'Visual effects reel',6:'DVD still'}[number]||'DVD title',audioStream:this.s[1],subtitleStream:this.s[2],duration:pgc?.duration.seconds};
  }
  route(d){
    this.tick();const p=this.pgcs.get(this.pgc),dom=p?.domain||'VTS01',lu=p?.language_unit||1;
    if(d.type==='LinkPGCN')return this.enter(`${dom}_LU${lu}_PGC${d.number}`);
    if(d.type==='LinkPGN')return this.program(d.number);
    if(d.type==='LinkCN')return this.showCell(d.number);
    if(d.type==='LinkSub'){
      if(d.button)this.s[8]=d.button*1024;
      switch(d.operation){
        case 'NoLink':return null;
        case 'TopCell':return this.showCell(this.cell);
        case 'NextCell':return this.cell<p.cells.length?this.showCell(this.cell+1):this.post();
        case 'PrevCell':return this.showCell(Math.max(1,this.cell-1));
        case 'TopProgram':return this.program(this.programNumber());
        case 'NextProgram':return this.program(this.programNumber()+1);
        case 'PrevProgram':return this.program(Math.max(1,this.programNumber()-1));
        case 'TopPGC':return this.enter(p.id);
        case 'TailPGC':return this.post();
        case 'NextPGC':return this.enter(`${dom}_LU${lu}_PGC${p.next_pgc}`);
        case 'PrevPGC':return this.enter(`${dom}_LU${lu}_PGC${p.previous_pgc}`);
        case 'GoUpPGC':return this.enter(`${dom}_LU${lu}_PGC${p.up_pgc}`);
        case 'Resume':return this.title(1);
      }
    }
    if(d.type==='JumpTT')return this.title(d.title);
    if(d.type==='JumpVTS_TT'||d.type==='JumpVTS_PTT'){
      const vts=Number(dom.slice(3)),t=this.archive.titles.find(t=>t.vts===vts&&t.vts_title===d.title);
      if(!t)throw Error('Unknown DVD title');return this.title(t.title,d.chapter||1);
    }
    if(d.type==='JumpSS'||d.type==='CallSS'){
      const domain=d.domain==='VTSM'?`VTS${String(d.vts||Number(dom.slice(3))||1).padStart(2,'0')}`:d.domain;
      if(domain==='FirstPlay')return this.list(this.archive.first_play.commands.pre||[]);
      const target=d.pgc?`${domain}_LU1_PGC${d.pgc}`:this.archive.pgcs.find(p=>p.domain===domain&&p.entry_menu===d.menu)?.id;
      if(!target)throw Error('Menu destination is unavailable');return this.enter(target);
    }
    if(d.type==='Exit')return {kind:'notice',message:'End of DVD navigation.'};
    throw Error('Unsupported DVD destination: '+d.type);
  }
  press(button){this.steps=0;const action=this.instruction(button.command);return action?.destination?this.route(action.destination):{kind:'asset',assetId:this.asset,pgcId:this.pgc,cellIndex:this.cell};}
  finish(){
    this.steps=0;const p=this.pgcs.get(this.pgc),c=p?.cells[this.cell-1];if(!c)return null;
    if(c.cell_command){const a=this.instruction(p.commands.cell[c.cell_command-1]);if(a?.destination)return this.route(a.destination);}
    return this.cell<p.cells.length?this.showCell(this.cell+1):this.post();
  }
  loops(){const p=this.pgcs.get(this.pgc),c=p?.cells[this.cell-1],cmd=c?.cell_command?p.commands.cell[c.cell_command-1]:null;
    return cmd?.destination?.type==='LinkSub'&&cmd.destination.operation==='TopProgram'&&p.program_map[this.programNumber()-1]===this.cell;
  }
}
