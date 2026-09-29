/* Runs inside the local gallery for verification, not in the delivered UI. */
function testNavigation(){
 const checks=[];const failures=[];let links=0;
 const assert=(ok,label)=>{if(!ok)throw Error(label);checks.push(label);};
 const b=(vm,n)=>vm.assets.get(vm.asset).button_states[0].buttons.find(b=>b.group===wideGroup(vm.assets.get(vm.asset))&&b.number===n);
 const press=(vm,n)=>vm.press(b(vm,n));
 const id=v=>`VTS01_VOB${String(v).padStart(2,'0')}_CELL01`;
 const vm=new MenuNavigation(archive,()=>0);
 vm.seed(id(40));assert(press(vm,1).assetId===id(54),'Character changes from 1 to 2');
 vm.seed(id(40));assert(press(vm,2).assetId===id(43),'Shirt changes to next authored combination');
 vm.seed(id(40));assert(press(vm,3).assetId===id(45),'Weapon changes to next authored combination');
 vm.seed(id(40));assert(press(vm,5).assetId===id(42),'Instructions opens');assert(press(vm,1).assetId===id(40),'Instructions returns to builder');
 vm.seed(id(40));assert(press(vm,9).assetId===id(12),'Setup opens');assert(press(vm,1).assetId===id(9),'Caption menu opens');assert(press(vm,2).assetId===id(12)&&vm.s[2]===65,'French selection returns to setup and retains selection');
 assert(press(vm,4).assetId===id(40),'Setup returns to current builder combination');
 vm.seed(id(53));press(vm,5);assert(press(vm,1).assetId===id(53),'Instructions preserves selected combination');
 vm.seed(id(40));assert(press(vm,7).assetId===id(1),'Scene selection opens');assert(press(vm,6).assetId===id(2),'Scene page 2 opens');assert(press(vm,1).chapter===5,'Scene selection targets chapter 5');
 vm.seed(id(40));assert(press(vm,8).assetId===id(6),'Bonus entrance transition opens');assert(vm.finish().assetId===id(8),'Bonus transition leads to menu');assert(press(vm,2).assetId===id(10),'Commentary menu opens');assert(press(vm,1).kind==='title'&&vm.s[1]===1,'Commentary on selects movie and audio stream');
 for(const [correct,intro,main] of [[49,34,35],[64,32,33],[69,36,37]]){
  vm.seed(id(correct));assert(press(vm,4).assetId===id(intro),'Correct '+correct+' activation selects correct entrance');assert(vm.finish().assetId===id(main),'Correct '+correct+' entrance leads to correct television menu');
 }
 vm.seed(id(40));assert(press(vm,4).assetId===id(26),'Incorrect activation selects random outcome');assert(vm.finish().assetId===id(40),'Outcome returns to selected combination');
 vm.seed(id(35));assert(press(vm,4).assetId===id(23),'Activated setup uses television style');assert(press(vm,4).assetId===id(35),'Activated setup returns to same television menu');
 vm.seed(id(35));press(vm,3);vm.finish();assert(vm.asset===id(19),'Activated bonus uses television style');assert(press(vm,3).assetId===id(40),'Character selection resets to builder');
 vm.seed(id(49));assert(vm.loops(),'Builder loops its current cell');const snapshot=vm.snapshot();press(vm,2);vm.restore(snapshot);assert(vm.asset===id(49)&&vm.g[9]===108,'History snapshot restores combination');
 for(const a of archive.assets){
  const buttons=a.button_states[0]?.buttons.filter(b=>b.group===wideGroup(a))||[];
  for(const button of buttons){
   const v=new MenuNavigation(archive,()=>0);v.seed(a.id);
   try{const out=v.press(button);if(out.kind==='asset'&&!byId.has(out.assetId))throw Error('Missing asset '+out.assetId);if(out.kind==='notice')throw Error(out.message);links++;}
   catch(e){failures.push({asset:a.id,button:button.number,message:e.message});}
  }
 }
 assert(failures.length===0,'Every widescreen menu button resolves');
 // Exercise real page controls, not only the command interpreter.
 openAsset(byId.get(id(40)));$('hotspots').querySelector('[data-button="9"]').click();assert(current.id===id(12),'On-screen Setup hotspot navigates');
 $('buttons').querySelector('[data-button="1"]').click();assert(current.id===id(9),'Sidebar Caption button navigates');
 $('hotspots').querySelector('[data-button="2"]').click();assert(current.id===id(12)&&menuNav.s[2]===65,'On-screen caption choice navigates back');
 assert(location.hash==='#asset='+id(12),'Menu page has a direct link');assert(history.state.canGoBack,'Back history is available');
 openAsset(byId.get(id(40)));const hotspot=$('hotspots').querySelector('[data-button="1"]');hotspot.focus();hotspot.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowDown',bubbles:true,cancelable:true}));assert(document.activeElement.dataset.button==='2','Arrow keys follow DVD directional links');
 $('hotspots').querySelector('[data-button="5"]').click();assert(current.id===id(42),'Instructions hotspot opens');
 $('hotspots').querySelector('[data-button="1"]').click();assert(current.id===id(40),'Instructions return hotspot opens builder');
 $('hotspots').querySelector('[data-button="6"]').click();if($('titlePanel').hidden)continueMenu();assert(!$('titlePanel').hidden,'Movie button presents external title destination');$('returnToMenu').click();assert(current.id===id(40)&&!externalReturn,'External destination returns to the interactive menu');assert(location.hash==='#asset='+id(40),'External return updates page link');
 $('video').pause();clearTimeout(finishTimer);finishTimer=null;
 return {status:'passed',button_routes:links,scenario_checks:checks,failures};
}
window.addEventListener('load',()=>{
 try{document.body.dataset.navigationTest=JSON.stringify(testNavigation());}
 catch(e){document.body.dataset.navigationTest=JSON.stringify({status:'failed',message:e.stack});}
});
