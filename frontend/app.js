const API = `${location.protocol}//${location.hostname}:8000/api`;
const $ = id => document.getElementById(id);
const form = $('search-form');
const palettes = ['#eee1cc','#edd5ce','#dce4d4','#e6dccc','#e8dbc5','#d5e4df'];
const money = value => value == null ? 'Price unavailable' : `₹${Number(value).toLocaleString('en-IN')} for two`;
function element(tag, className, text) { const node=document.createElement(tag); if(className) node.className=className; if(text!==undefined) node.textContent=text; return node; }
function dishFor(cuisines) { const text=(cuisines||[]).join(' '); if(/pizza|italian/i.test(text)) return '🍕'; if(/bakery|dessert|ice cream/i.test(text)) return '🍰'; if(/cafe|coffee/i.test(text)) return '☕'; if(/chinese|thai|asian/i.test(text)) return '🍜'; if(/burger|american/i.test(text)) return '🍔'; return '🍛'; }
function render(restaurants, ranked=false) {
  $('results').replaceChildren(); $('empty').hidden=restaurants.length>0;
  $('result-count').textContent=`${restaurants.length} places to explore`;
  restaurants.forEach((r,index)=>{
    const card=element('article','card'); const art=element('div','card-art'); art.style.setProperty('--card-bg',palettes[index%palettes.length]);
    const dish=element('span','dish',dishFor(r.cuisines)); dish.setAttribute('aria-hidden','true'); art.append(dish);
    art.append(element('span','rank',ranked?`✦ YOUR PICK #${index+1}`:'LOCAL FAVOURITE'));
    const body=element('div','card-body'), heading=element('div','card-heading');
    heading.append(element('h3','',r.name),element('span','rating',`${Number(r.rating).toFixed(1)} ★`));
    body.append(heading,element('p','card-meta',`${(r.cuisines||[]).map(c=>c[0].toUpperCase()+c.slice(1)).join(' · ')}\n${r.location||r.city}`));
    const details=element('div','card-details'); details.append(element('span','',money(r.cost_for_two)),element('span','',`${Number(r.votes).toLocaleString()} votes`)); body.append(details);
    if(r.explanation) body.append(element('p','explanation',r.explanation));
    if(r.trade_offs) body.append(element('p','tradeoff',r.trade_offs));
    card.append(art,body); $('results').append(card);
  });
}
async function request(path,options) {
 const response=await fetch(API+path,{...options,signal:AbortSignal.timeout(60000)});
 if(!response.ok) { let message='The request could not be completed.'; try { const data=await response.json(); if(typeof data.detail==='string')message=data.detail; }catch{} throw new Error(message); }
 return response.json();
}
async function init() {
 try {
  const [options,data]=await Promise.all([request('/options'),request('/restaurants')]);
  $('location').replaceChildren(...options.locations.map(name=>new Option(name,name)));
  $('location').value=options.locations.includes('Bangalore')?'Bangalore':options.locations[0];
  $('cuisine').replaceChildren(new Option('All cuisines','Any'),...options.cuisines.map(name=>new Option(name,name)));
  $('location').disabled=false; $('cuisine').disabled=false; $('submit').disabled=false;
  $('status').textContent='A few highly rated places to get you started. Add your preferences for a personal shortlist.';
  render(data.restaurants);
 } catch(error) { $('status').textContent='We couldn’t connect to the restaurant service. Check that the backend is running, then try again.'; const retry=element('button','','Try again'); retry.type='button'; retry.onclick=()=>{retry.remove(); init();}; $('status').append(' ',retry); }
}
document.querySelectorAll('[data-note]').forEach(button=>button.onclick=()=>{ $('notes').value=button.dataset.note; $('notes').focus(); });
form.onsubmit=async event=>{
 event.preventDefault(); const button=$('submit'); button.disabled=true; button.textContent='Finding your favourites…'; form.setAttribute('aria-busy','true');
 $('status').textContent='Matching your preferences and asking AI to pick your favourites…'; $('notice').hidden=true; $('results').replaceChildren(); $('empty').hidden=true;
 $('result-title').textContent='A little closer to your perfect table.'; $('result-eyebrow').textContent='CURATED AROUND YOU'; $('result-count').textContent='';
 try {
  const data=await request('/recommendations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({location:$('location').value,cuisine:$('cuisine').value,budget:$('budget').value,min_rating:Number($('rating').value),extra_prefs:$('notes').value})});
  $('status').textContent=data.summary;
  const notices=[data.notice,data.fallback_triggered?data.fallback_reason:''].filter(Boolean);
  $('notice').textContent=notices.join(' '); $('notice').hidden=!notices.length;
  render(data.recommendations,data.ai_ranking); $('discover').scrollIntoView({behavior:'smooth',block:'start'});
 } catch(error) { $('status').textContent=`We couldn’t finish your search. ${error.message} Please try again.`; }
 finally { button.disabled=false; button.textContent='Find my favourites ↗'; form.removeAttribute('aria-busy'); }
};
init();
