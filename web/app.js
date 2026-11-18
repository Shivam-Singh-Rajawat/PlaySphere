/* PlaySphere 2.0 — dependency-free progressive single-page UI. */
'use strict';
const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const safeUrl = (url) => { try { const u = new URL(url, location.origin); return ['https:', 'http:'].includes(u.protocol) || (u.origin === location.origin && u.pathname.startsWith('/api/videos/')) ? u.href : '#'; } catch { return '#'; } };
const sportIcon = (sport) => ({football:'⚽', basketball:'🏀', cricket:'🏏', badminton:'🏸', tennis:'🎾', athletics:'🏃', volleyball:'🏐'})[String(sport || '').toLowerCase()] || '🏅';
const dateLabel = (iso) => { const d = new Date(`${iso}T12:00:00`); return Number.isNaN(d.getTime()) ? 'TBA' : d.toLocaleDateString('en-IN', {day:'numeric', month:'short', year:'numeric'}); };
const dateParts = (iso) => { const d = new Date(`${iso}T12:00:00`); return {day: d.toLocaleDateString('en-IN', {day:'2-digit'}), month:d.toLocaleDateString('en-IN', {month:'short'}).toUpperCase()}; };
const state = { token: sessionStorage.getItem('ps_token') || '', user: null, players: [], tournaments: [], stats: {}, registrations: [], shortlist: [], evaluations: [], myVideos: [], myAchievements: [], activeStatus: 'upcoming', loading: true, modal: '', selectedPlayer: null };
let toastTimer;

async function api(path, { method='GET', body, form=false, ...rest }={}) {
  const headers = { ...(state.token ? {Authorization: `Bearer ${state.token}`} : {}), ...(form ? {} : {'Content-Type':'application/json'}), ...(rest.headers || {}) };
  const response = await fetch(path, {method, headers, ...(body === undefined ? {} : {body:form ? body : JSON.stringify(body)}), ...rest});
  if (response.status === 204) return null;
  let payload;
  try { payload = await response.json(); } catch { payload = null; }
  if (!response.ok) {
    const detail = payload?.detail;
    const error = Array.isArray(detail) ? detail.map((x) => `${x.loc?.at(-1) || 'Field'}: ${x.msg}`).join(' · ') : (typeof detail === 'string' ? detail : `Request failed (${response.status})`);
    const exception = new Error(error);
    exception.status = response.status;
    throw exception;
  }
  return payload;
}
function toast(message, isError=false) {
  const el = $('#toast'); clearTimeout(toastTimer);
  el.textContent = message; el.classList.toggle('error', isError); el.classList.add('visible');
  toastTimer = setTimeout(() => el.classList.remove('visible'), 4100);
}
function roleIs(...roles) { return !!state.user && roles.includes(state.user.role); }
function loginUser(data) {
  state.token = data.token; state.user = data.user; sessionStorage.setItem('ps_token', data.token);
  renderNav(); updateWorkspace();
}
function logout() {
  state.token = ''; state.user = null; state.registrations = []; state.shortlist = []; state.evaluations = []; state.myVideos = []; state.myAchievements = [];
  sessionStorage.removeItem('ps_token'); renderNav(); updateWorkspace(); renderPlayers(); renderTournaments();
  toast('You have been logged out.');
}
async function fetchAll() {
  const results = await Promise.allSettled([api('/api/players'), Promise.all(['upcoming','live','recent'].map(status => api(`/api/tournaments?status=${status}`))).then(groups => groups.flat()), api('/api/stats')]);
  const keys = ['players','tournaments','stats'];
  results.forEach((result,i) => { if(result.status === 'fulfilled') state[keys[i]] = result.value; else toast(`Could not load ${keys[i]}. Please refresh.`, true); });
  state.loading = false; renderPlayers(); renderTournaments();
  if(state.user) await fetchMyData();
}
async function fetchMyData() {
  if (!state.user) return;
  const requests = state.user.role === 'player'
    ? [['registrations','/api/tournaments/me/registrations'],['myVideos','/api/players/me/videos'],['myAchievements',`/api/players/${state.user.id}`]]
    : [['shortlist','/api/scouting/shortlist'],['evaluations','/api/scouting/my-evaluations']];
  const results = await Promise.allSettled(requests.map(([,path])=>api(path)));
  results.forEach((r,i) => { if(r.status === 'fulfilled') state[requests[i][0]] = requests[i][0] === 'myAchievements' ? r.value.achievements : r.value; });
  renderPlayers(); renderTournaments(); updateWorkspace();
}
function renderNav() {
  const nav = $('#nav-actions');
  if (!state.user) { nav.innerHTML = '<button class="text-button" data-action="login">Log in</button><button class="btn btn-dark btn-sm" data-action="register">Join PlaySphere <span>↗</span></button>'; return; }
  nav.innerHTML = `<button class="text-button" data-action="logout">Log out</button><a class="btn btn-dark btn-sm" href="#my-space">${esc(state.user.name.split(' ')[0])}'s space <span>↗</span></a>`;
}
function empty(icon, title, message, action='register', cta='Create your profile') {
  return `<div class="empty-state"><span class="empty-icon">${icon}</span><h3>${esc(title)}</h3><p>${esc(message)}</p><button class="btn btn-dark" data-action="${esc(action)}">${esc(cta)} <span>↗</span></button></div>`;
}
function playerCard(p,i) {
  const values = Object.entries(p.stats || {}).slice(0,2);
  const age = p.age ? ` · Age ${esc(p.age)}` : '';
  const isSelf = state.user?.id === p.id;
  const isSaved = state.shortlist.some(x=>x.id === p.id);
  return `<article class="player-card reveal is-visible" style="transition-delay:${Math.min(i,5)*50}ms"><div class="player-card-cover"><span class="card-texture">✳</span><span class="player-sport-ball" aria-hidden="true">${sportIcon(p.sport)}</span><div class="card-cover-top"><span class="pill pill-light">${esc(p.sport || 'Multi-sport')}</span><span class="card-serial">PS / ${String(p.id).padStart(3,'0')}</span></div></div><div class="player-card-content"><div class="player-topline"><h3>${esc(p.name)}</h3><span class="player-age">${age}</span></div><p class="player-subtitle">${esc(p.position || 'Athlete')} ${p.city ? '· '+esc(p.city) : ''}</p><div class="player-card-stats">${values.length ? values.map(([k,v])=>`<span><b>${esc(v)}</b>${esc(k)}</span>`).join('') : '<span><b>Ready</b> Player profile</span><span><b>Open</b> To opportunities</span>'}</div><div class="player-card-actions"><button class="link-button" data-action="view-player" data-id="${p.id}">${isSelf ? 'View my profile' : 'View player profile'} <span>↗</span></button>${roleIs('scout','coach','club') ? `<button class="icon-button" aria-label="${isSaved?'Remove from shortlist':'Add to shortlist'}" title="${isSaved?'Remove from shortlist':'Shortlist'}" data-action="${isSaved?'unshortlist':'shortlist'}" data-id="${p.id}">${isSaved?'★':'☆'}</button>` : ''}</div></div></article>`;
}
function renderPlayers() {
  const target = $('#players-grid'); const search = ($('#player-search')?.value || '').toLowerCase().trim(); const sport = $('#player-sport')?.value || '';
  if (state.loading) return;
  const players = state.players.filter(p => (!sport || p.sport.toLowerCase() === sport.toLowerCase()) && (!search || `${p.name} ${p.city} ${p.position}`.toLowerCase().includes(search)));
  target.innerHTML = players.length ? players.map(playerCard).join('') : empty('🏅', search || sport ? 'No players match this search yet.' : 'Be the first to get discovered.', search || sport ? 'Try another sport or search term to find your next talent.' : 'Start the directory with your own player portfolio — no fake profiles or fabricated performance stats.', search || sport ? 'reset-players' : 'register', search || sport ? 'Clear filters' : 'Join as a player');
}
function tournamentCard(t) {
  const {day,month} = dateParts(t.start_date);
  const joined = state.registrations.some(x=>x.id === t.id);
  const badge = {upcoming:'pill-success',live:'pill-warning',recent:'pill-muted'}[t.status];
  const button = roleIs('player') && joined ? `<button class="btn btn-outline" data-action="withdraw" data-id="${t.id}">Withdraw <span>↗</span></button>` :
                 roleIs('player') && t.registration_open ? `<button class="btn btn-dark" data-action="join-tournament" data-id="${t.id}">Register now <span>↗</span></button>` :
                 !state.user && t.registration_open ? `<button class="btn btn-dark" data-action="login">Sign in to join <span>↗</span></button>` :
                 `<span class="pill pill-muted">${t.status === 'recent' ? 'Completed' : t.registration_open ? 'Player registration' : 'Closed / full'}</span>`;
  return `<article class="tournament-card"><div class="tournament-date"><span class="month">${esc(month)}</span><strong>${esc(day)}</strong></div><div class="tournament-main"><span class="pill ${badge}">${esc(t.status === 'live' ? '● LIVE NOW' : t.status.toUpperCase())} · ${esc(t.sport)}</span><h3>${esc(t.title)}</h3><p>${esc(t.description || t.level)}</p></div><div class="tournament-info"><span>⌖ &nbsp; ${esc(t.location)}</span><span>◷ &nbsp; ${dateLabel(t.start_date)}${t.end_date !== t.start_date ? ' – '+dateLabel(t.end_date):''}</span><span>♙ &nbsp; ${t.participants_count}/${t.capacity} registered</span></div><div class="tournament-action">${button}<small>Deadline: ${dateLabel(t.registration_deadline)}</small></div></article>`;
}
function renderTournaments() {
  const root = $('#tournaments-list');
  if (state.loading) return;
  const sport = $('#tournament-sport')?.value || '';
  const events = state.tournaments.filter(t => t.status === state.activeStatus && (!sport || t.sport.toLowerCase() === sport.toLowerCase()));
  root.innerHTML = events.length ? events.map(tournamentCard).join('') : empty('🏆', state.activeStatus === 'upcoming' ? 'Your next tournament starts here.' : state.activeStatus === 'live' ? 'No games are live right now.' : 'No recent tournaments listed.', state.activeStatus === 'upcoming' ? 'New competitions are added by coaches and clubs. Check back soon or start an event.' : 'Switch tournament tabs to explore other competitions.', roleIs('club','coach') ? 'create-tournament':'register', roleIs('club','coach') ? 'Post a tournament' : 'Join the community');
  $$('.tab').forEach(b=>{const active=b.dataset.tab===state.activeStatus;b.classList.toggle('active',active);b.setAttribute('aria-pressed',String(active));});
  $('#create-event-button').title = roleIs('club','coach') ? 'Create tournament' : 'Coach or club account required';
}
function updateWorkspace() {
  const section = $('#my-space');
  section.classList.toggle('hidden', !state.user);
  if (!state.user) return;
  $('#dashboard-welcome').textContent = `Welcome back, ${state.user.name}. Your ${state.user.role} workspace is ready.`;
  const isPlayer = state.user.role === 'player';
  const cards = isPlayer ? `
    <div class="dash-card dash-highlight"><div class="dash-stat">${state.myVideos.length}</div><div class="dash-stat-label">VIDEOS IN YOUR PORTFOLIO</div><p>Give scouts something real to see. Upload match footage or add a link.</p><button class="btn btn-lime" data-action="add-video">Add video <span>↗</span></button></div>
    <div class="dash-card"><div class="dash-stat">${state.registrations.length}</div><div class="dash-stat-label">TOURNAMENT REGISTRATIONS</div><p>Track all the competitions you've signed up for.</p><a class="btn btn-outline" href="#tournaments">Find more <span>↗</span></a></div>
    <div class="dash-card"><div class="dash-stat">${Object.keys(state.user.stats || {}).length}</div><div class="dash-stat-label">PERFORMANCE STATS</div><p>Keep your personal stats and position up to date.</p><button class="btn btn-outline" data-action="edit-profile">Edit profile <span>↗</span></button></div>
    <div class="dash-card wide"><h3>Your player toolkit</h3><p>Add highlights, achievement evidence and a strong player bio so recruiters can evaluate the complete picture.</p><div class="dash-actions"><button class="btn btn-dark" data-action="add-video">+ Add footage</button><button class="btn btn-outline" data-action="add-achievement">+ Add achievement</button><button class="btn btn-outline" data-action="view-player" data-id="${state.user.id}">View my page ↗</button></div></div>
    <div class="dash-card wide"><h3>My match footage</h3><p>Manage your uploaded films and video evidence. Private cloud files only open after an authenticated, time-limited request.</p><ul class="dash-list">${state.myVideos.length ? state.myVideos.map(v=>`<li><span><strong>${esc(v.title)}</strong><br><small>${esc(v.kind)} · ${esc(v.visibility)}</small></span><span class="dash-actions"><button data-action="watch-video" data-id="${v.id}">Watch ↗</button><button data-action="delete-video" data-id="${v.id}" aria-label="Delete ${esc(v.title)}">Delete</button></span></li>`).join('') : '<li>No footage added yet. Upload a highlight to get started.</li>'}</ul></div>
    <div class="dash-card wide"><h3>My achievements</h3><p>Show the awards and certificates that back up your game. Achievements remain labelled unverified.</p><ul class="dash-list">${state.myAchievements.length ? state.myAchievements.map(a=>`<li><span><strong>${esc(a.title)}</strong><br><small>${esc(a.issuer)} · ${a.year} · ${a.verified?'Verified':'Unverified'} ${a.evidence_url?`· <a href="${esc(safeUrl(a.evidence_url))}" target="_blank" rel="noopener noreferrer">View evidence ↗</a>`:''}</small></span><button data-action="delete-achievement" data-id="${a.id}" aria-label="Remove ${esc(a.title)}">Remove</button></li>`).join('') : '<li>No achievements added yet. Record your best moments.</li>'}</ul><button class="btn btn-outline" data-action="add-achievement">+ Add achievement</button></div>
    <div class="dash-card"><h3>My tournaments</h3><ul class="dash-list">${state.registrations.length ? state.registrations.slice(0,4).map(t=>`<li><span>${esc(t.title)}<br><small>${dateLabel(t.start_date)}</small></span><button data-action="withdraw" data-id="${t.id}">Withdraw</button></li>`).join('') : '<li>No registrations yet. Explore tournaments to get started.</li>'}</ul></div>` : `
    <div class="dash-card dash-highlight"><div class="dash-stat">${state.shortlist.length}</div><div class="dash-stat-label">SHORTLISTED PLAYERS</div><p>Review talent consistently. Your shortlist is private to you.</p><a class="btn btn-lime" href="#discover">Browse players <span>↗</span></a></div>
    <div class="dash-card"><div class="dash-stat">${state.evaluations.length}</div><div class="dash-stat-label">COMPLETED EVALUATIONS</div><p>Track your four-dimension scouting reports.</p><a class="btn btn-outline" href="#discover">Evaluate talent <span>↗</span></a></div>
    <div class="dash-card"><div class="dash-stat">${state.tournaments.filter(x=>x.owner_id===state.user.id).length}</div><div class="dash-stat-label">MY TOURNAMENTS</div><p>Clubs and coaches can publish real events for players.</p>${roleIs('club','coach') ? '<button class="btn btn-outline" data-action="create-tournament">Post event <span>↗</span></button>' : '<p>Event publishing is for coaches and clubs.</p>'}</div>
    <div class="dash-card wide"><h3>My scouting shortlist</h3><ul class="dash-list">${state.shortlist.length ? state.shortlist.map(p=>`<li><span>${esc(p.name)} <small>· ${esc(p.sport)}</small></span><button data-action="view-player" data-id="${p.id}">Review ↗</button></li>`).join('') : '<li>No shortlisted athletes yet. Browse the player directory.</li>'}</ul></div>
    <div class="dash-card"><h3>My assessments</h3><ul class="dash-list">${state.evaluations.length ? state.evaluations.slice(0,8).map(e=>`<li><span>${esc(e.player_name)}<br><small>${e.score} / 5 · Private assessment</small></span><button data-action="evaluate" data-id="${e.player_id}">Review / edit ↗</button></li>`).join('') : '<li>Your written assessments will appear here.</li>'}</ul></div>
    ${roleIs('coach','club') ? `<div class="dash-card wide"><h3>My organized tournaments</h3><p>See which athletes have registered for events you manage.</p><ul class="dash-list">${state.tournaments.filter(t=>t.owner_id===state.user.id).length ? state.tournaments.filter(t=>t.owner_id===state.user.id).map(t=>`<li><span><strong>${esc(t.title)}</strong><br><small>${dateLabel(t.start_date)} · ${t.participants_count}/${t.capacity} registered</small></span><button data-action="view-registrations" data-id="${t.id}">View entrants ↗</button></li>`).join('') : '<li>You have not posted a tournament yet.</li>'}</ul></div>` : ''}`;
  $('#dashboard-body').innerHTML = `<div class="dashboard-grid">${cards}</div>`;
}
function field(name,label,type='text',value='',extra='') {
  const tag = type==='textarea' ? `<textarea id="f-${name}" name="${name}" ${extra}>${esc(value)}</textarea>` : type==='select' ? `<select id="f-${name}" name="${name}" ${extra}>${value}</select>` : `<input id="f-${name}" name="${name}" type="${type}" value="${esc(value)}" ${extra}>`;
  return `<div class="field"><label for="f-${name}">${esc(label)}</label>${tag}</div>`;
}
const sportOptions = (current='') => ['Football','Basketball','Cricket','Badminton','Tennis','Athletics','Volleyball','Other'].map(s=>`<option ${s===current?'selected':''}>${s}</option>`).join('');
const modalHeading = (kicker,title,subtitle='') => `<span class="modal-kicker">✳ ${esc(kicker)}</span><h2 id="modal-title">${esc(title)}</h2><p class="modal-subtitle">${esc(subtitle)}</p>`;
function openModal(type, payload={}) {
  state.modal = type;
  const root = $('#modal-content');
  $('#modal-window').classList.toggle('modal-wide',type==='view-player');
  if (type==='register') root.innerHTML = `${modalHeading('JOIN THE MOVEMENT','Your journey starts here.','Sign up as a player, scout, coach, or club. Every great opportunity starts with a profile.')}<form class="form-stack" data-form="register">${field('name','Full name / Organization name','text','','required minlength="2" maxlength="120" autocomplete="name"')}${field('email','Email address','email','','required autocomplete="email"')}${field('password','Password (10+ characters)','password','','required minlength="10" autocomplete="new-password"')}${field('role','I am joining as','select',`<option value="player">Player</option><option value="coach">Coach</option><option value="scout">Scout</option><option value="club">Club / Organizer</option>`)}${field('sport','Primary sport','select',sportOptions())}<p class="form-hint">Coach, scout and club affiliations are self-declared. Always verify identity independently before recruitment decisions.</p><button type="submit" class="btn btn-dark btn-large">Create my account ↗</button><div class="form-switch">Already signed up? <button type="button" data-action="login">Log in</button></div></form>`;
  else if (type==='login') root.innerHTML = `${modalHeading('WELCOME BACK','Good to have you back.','Pick up where you left off. Your next opportunity is one login away.')}<form class="form-stack" data-form="login">${field('email','Email address','email','','required autocomplete="email"')}${field('password','Password','password','','required autocomplete="current-password"')}<button class="btn btn-dark btn-large" type="submit">Log in to my space ↗</button><div class="form-switch">New to PlaySphere? <button type="button" data-action="register">Create an account</button></div></form>`;
  else if (type==='edit-profile') { const u=state.user || {}; root.innerHTML = `${modalHeading('PLAYER PORTFOLIO','Make your game known.','Tell scouts what you do best. Everything here is public except your email.') }<form data-form="profile" class="form-stack"><div class="form-grid">${field('sport','Sport','select',sportOptions(u.sport))}${field('age','Age','number',u.age||'','min="13" max="100"')}${field('city','City','text',u.city||'','maxlength="100"')}${field('position','Position / Playing role','text',u.position||'','maxlength="100"')}</div>${field('bio','About your game','textarea',u.bio||'','maxlength="1800"')}${field('stats','Stats (e.g. Goals: 12, Assists: 5)','text',Object.entries(u.stats||{}).map(([k,v])=>`${k}: ${v}`).join(', '),'maxlength="1000"')}<button class="btn btn-dark btn-large" type="submit">Save my profile ↗</button></form>`; }
  else if (type==='add-video') root.innerHTML = `${modalHeading('PUT IT ON FILM','Let the footage speak.','Upload a short match or training clip, or share a secure HTTPS link.')}<form data-form="video" class="form-stack">${field('title','Video title','text','','required maxlength="160" minlength="2"')}${field('kind','Type of footage','select','<option value="highlight">Highlights</option><option value="match">Full match / match clip</option><option value="training">Training / skill drill</option>')}${field('visibility','Visibility','select','<option value="public">Public — visible to scouts</option><option value="private">Private — hidden from public profiles</option>')}<div class="video-switch"><label><input type="radio" name="source" value="link" checked> Video link</label><label><input type="radio" name="source" value="upload"> Upload video</label></div><div class="video-group" id="video-link-group">${field('url','HTTPS video URL','url','','placeholder="https://www.youtube.com/watch?v=…"')}</div><div class="video-group" id="video-upload-group" hidden>${field('file','Select MP4, WebM or MOV (up to 100 MB with cloud storage)','file','','accept="video/mp4,video/webm,video/quicktime"')}<p class="form-hint">Cloud uploads support up to 100 MB when configured. Local uploads allow 25 MB. External private video links depend on your video host’s permissions.</p></div><button class="btn btn-dark btn-large" type="submit">Add to portfolio ↗</button></form>`;
  else if (type==='add-achievement') root.innerHTML = `${modalHeading('THE MILESTONES','Show what you earned.','Add competitions, medals, certificates and other accomplishments. All claims are labelled unverified until independently checked.')}<form data-form="achievement" class="form-stack">${field('title','Achievement title','text','','required minlength="2" maxlength="160"')}${field('issuer','Issuing event / organization','text','','required minlength="2" maxlength="160"')}<div class="form-grid">${field('year','Year','number',new Date().getFullYear(),'required min="1950" max="2100"')}${field('evidence_url','Evidence link (optional)','url','','placeholder="https://…"')}</div><button class="btn btn-dark btn-large" type="submit">Add achievement ↗</button></form>`;
  else if (type==='create-tournament') {const next = new Date(Date.now()+14*86400000); const nextTwo = new Date(Date.now()+16*86400000); const prev = new Date(Date.now()+12*86400000); const iso=d=>d.toISOString().slice(0,10); root.innerHTML = `${modalHeading('MAKE IT HAPPEN','Host the next big game.','Publish a tournament where players can discover and register for your event.')}<form data-form="tournament" class="form-stack">${field('title','Tournament name','text','','required minlength="3" maxlength="180"')}<div class="form-grid">${field('sport','Sport','select',sportOptions())}${field('level','Level','select','<option>Open</option><option>District</option><option>State</option><option>Regional</option><option>National</option>')}${field('location','Location / Venue','text','','required minlength="2" maxlength="160"')}${field('capacity','Max players','number','100','required min="1" max="5000"')}${field('start_date','Start date','date',iso(next),'required')}${field('end_date','End date','date',iso(nextTwo),'required')}${field('registration_deadline','Registration closes','date',iso(prev),'required')}</div>${field('description','Event description','textarea','','maxlength="3000"')}<button class="btn btn-dark btn-large" type="submit">Publish tournament ↗</button></form>`; }
  else if (type==='evaluate') { const p=payload.player; root.innerHTML = `${modalHeading('SCOUT EVALUATION',`Evaluate ${p.name}`,'Use the same four 1–5 dimensions for every player. Scores and notes are visible only to you; no automatic selection decisions.') }<form data-form="evaluate" class="form-stack" data-id="${p.id}">${['technique','teamwork','consistency','potential'].map(k=>field(k,k.charAt(0).toUpperCase()+k.slice(1)+' · 1–5','select',[1,2,3,4,5].map(n=>`<option value="${n}" ${n===3?'selected':''}>${n} / 5</option>`).join(''))).join('')}${field('notes','Evidence and scouting notes','textarea','','maxlength="2000"')}<button type="submit" class="btn btn-dark btn-large">Save assessment ↗</button></form>`; }
  else if (type==='view-player') {root.innerHTML = `${modalHeading('PLAYER PORTFOLIO','Loading athlete…')}<div class="loading-state">Loading player profile…</div>`;}
  else return;
  $('#modal-shell').hidden=false;
  document.body.style.overflow='hidden';
  $('#modal-window').scrollTop=0;
  const first = $('input:not([type=hidden]),select,textarea',root); (first || $('#modal-window')).focus({preventScroll:true});
  if (type==='view-player') loadPlayerDetail(payload.id);
}
function closeModal() { $('#modal-shell').hidden=true;document.body.style.overflow='';state.modal='';state.selectedPlayer=null; }
async function loadPlayerDetail(id) {
  try {
    const p = await api(`/api/players/${id}`); if (state.modal!=='view-player') return;
    state.selectedPlayer=p;
    const achievements = p.achievements.length ? p.achievements.map(a=>`<div class="detail-item"><div><strong>🏅 ${esc(a.title)}</strong><small>${esc(a.issuer)} · ${a.year} · ${a.verified?'Verified':'Self-reported / unverified'}</small></div>${a.evidence_url?`<a href="${esc(safeUrl(a.evidence_url))}" target="_blank" rel="noopener noreferrer">Evidence ↗</a>`:''}${state.user?.id===p.id?`<button class="link-button" data-action="delete-achievement" data-id="${a.id}">Remove</button>`:''}</div>`).join('') : '<p class="detail-bio">No achievements added yet.</p>';
    const videos = p.videos.length ? p.videos.map(v=>`<div class="detail-item"><div><strong>▶ ${esc(v.title)}</strong><small>${esc(v.kind)} · ${dateLabel(v.created_at.slice(0,10))}</small></div><a href="${esc(safeUrl(v.url))}" target="_blank" rel="noopener noreferrer">Watch ↗</a></div>${v.uploaded?`<video class="video-preview" src="${esc(safeUrl(v.url))}" controls playsinline preload="none" aria-label="${esc(v.title)}"></video>`:''}`).join('') : '<p class="detail-bio">No public videos uploaded yet.</p>';
    const metrics = Object.entries(p.stats||{}).map(([k,v])=>`<span>${esc(k)} · ${esc(v)}</span>`).join('');
    const buttons = roleIs('coach','scout','club') ? `<button class="btn btn-dark" data-action="evaluate" data-id="${p.id}">Evaluate player ↗</button><button class="btn btn-outline" data-action="shortlist" data-id="${p.id}">★ Shortlist</button>` : state.user?.id===p.id ? `<button class="btn btn-dark" data-action="edit-profile">Edit profile ↗</button><button class="btn btn-outline" data-action="add-video">Add footage</button>` : '';
    $('#modal-content').innerHTML = `<span class="modal-kicker">✳ ATHLETE PROFILE / PS${String(p.id).padStart(3,'0')}</span><div class="detail-heading"><div class="detail-avatar">${sportIcon(p.sport)}</div><div><h2 id="modal-title">${esc(p.name)}</h2><span class="detail-subheading">${esc(p.sport || 'Athlete')} ${p.position?'· '+esc(p.position):''} ${p.city?'· '+esc(p.city):''} ${p.age?'· '+p.age+' years':''}</span></div></div><p class="detail-bio">${esc(p.bio || 'This player has not written a bio yet.')}</p><div class="detail-metrics">${metrics}</div><div class="detail-section"><h3>🎬 Match footage & highlights</h3>${videos}</div><div class="detail-section"><h3>🏆 Achievements & evidence</h3>${achievements}</div><div class="modal-actions">${buttons}</div>`;
  } catch (error) { $('#modal-content').innerHTML = `<h2 id="modal-title">Could not load player</h2><p class="modal-subtitle">${esc(error.message)}</p>`; }
}
function requireSignIn(action) {
  if (!state.user) { openModal('login');toast(`Sign in to ${action}.`);return false; }
  return true;
}
async function runAction(action,id) {
  try {
    if (action==='close-modal') return closeModal();
    if (action==='login' || action==='register') return openModal(action);
    if (action==='logout') return logout();
    if (action==='reset-players') {$('#player-search').value='';$('#player-sport').value='';return renderPlayers();}
    if (action==='view-player') return openModal('view-player',{id:Number(id)});
    if (action==='add-video' || action==='add-achievement' || action==='edit-profile') {if(!requireSignIn('manage your portfolio'))return;if(!roleIs('player'))throw new Error('Only player accounts can edit portfolios.');return openModal(action);}
    if (action==='create-tournament') {if(!requireSignIn('post tournaments'))return;if(!roleIs('club','coach'))throw new Error('Only clubs and coaches can post tournaments.');return openModal(action);}
    if (action==='evaluate') {if(!requireSignIn('evaluate players'))return;if(!roleIs('coach','club','scout'))throw new Error('Scout account required.');const player = state.selectedPlayer?.id===Number(id)?state.selectedPlayer:state.players.find(p=>p.id===Number(id));return openModal('evaluate',{player});}
    if (['shortlist','unshortlist'].includes(action)) {if(!requireSignIn('shortlist players'))return;if(!roleIs('scout','coach','club'))throw new Error('Recruiter account required.');await api(`/api/scouting/${id}/shortlist`,{method:action==='shortlist'?'POST':'DELETE'});await fetchMyData();toast(action==='shortlist'?'Player saved to your shortlist.':'Player removed from shortlist.');return;}
    if (['join-tournament','withdraw'].includes(action)) {if(!requireSignIn('register for tournaments'))return;if(!roleIs('player'))throw new Error('Tournament registration requires a player account.');if(action==='withdraw'&&!confirm('Withdraw your tournament registration?'))return;await api(`/api/tournaments/${id}/register`,{method:action==='withdraw'?'DELETE':'POST'});await fetchAll();toast(action==='withdraw'?'Tournament registration withdrawn.':'You are registered! Good luck.');return;}
    if (action==='watch-video') {
      if (!requireSignIn('watch your videos')) return;
      const video=state.myVideos.find(v=>v.id===Number(id));
      if(!video) throw new Error('Video no longer exists.');
      const tab=window.open('about:blank','_blank');
      try {
        let url=video.url;
        if(video.storage==='cloud') {
          url=(await api(`/api/videos/${id}/access`)).url;
        } else if(video.storage==='local'&&video.visibility==='private') {
          const response=await fetch(`/api/videos/${id}/file`,{headers:{Authorization:`Bearer ${state.token}`}});
          if(!response.ok) throw new Error('Private video could not be loaded.');
          url=URL.createObjectURL(await response.blob());
        }
        if(tab) tab.location.href=url.startsWith('blob:')?url:safeUrl(url);
        else window.location.href=url.startsWith('blob:')?url:safeUrl(url);
      } catch(error) { if(tab)tab.close(); throw error; }
      return;
    }
    if (action==='delete-video') {
      if (!requireSignIn('manage your videos')) return;
      if (!confirm('Permanently delete this video from your portfolio and cloud storage?')) return;
      await api(`/api/videos/${id}`, {method:'DELETE'});
      await fetchMyData(); await fetchAll(); toast('Video deleted.'); return;
    }
    if (action==='delete-achievement') {if(!confirm('Remove this achievement?'))return;await api(`/api/achievements/${id}`,{method:'DELETE'});if(state.modal==='view-player'&&state.selectedPlayer)await loadPlayerDetail(state.selectedPlayer.id);toast('Achievement removed.');return;}
  } catch (error) {toast(error.message,true);}
}
async function submitForm(form) {
  const data = Object.fromEntries(new FormData(form));
  const submit = $('button[type=submit]',form);
  const originalSubmitText = submit?.textContent;
  if (submit) submit.disabled=true;
  try {
    if (form.dataset.form==='login' || form.dataset.form==='register') {
      const response = await api(`/api/auth/${form.dataset.form}`,{method:'POST',body:form.dataset.form==='register'?{name:data.name,email:data.email,password:data.password,role:data.role,sport:data.sport}:{email:data.email,password:data.password}});
      loginUser(response); await fetchMyData(); closeModal(); await fetchAll();toast(`Welcome ${response.user.name.split(' ')[0]}!`);$('#my-space').scrollIntoView({behavior:'smooth'});return;
    }
    if (form.dataset.form==='profile') {
      const stats = {}; String(data.stats||'').split(',').forEach(part=>{const colon=part.indexOf(':');if(colon>0){const k=part.slice(0,colon).trim(),v=part.slice(colon+1).trim();if(k&&v)stats[k]=v;}});
      state.user = await api('/api/players/me',{method:'PATCH',body:{sport:data.sport,age:data.age?Number(data.age):null,city:data.city,position:data.position,bio:data.bio,stats}});
      await fetchAll(); closeModal();updateWorkspace();toast('Player profile updated.');return;
    }
    if (form.dataset.form==='achievement') {
      await api('/api/achievements',{method:'POST',body:{title:data.title,issuer:data.issuer,year:Number(data.year),evidence_url:data.evidence_url||null}});
      closeModal();toast('Achievement added. Evidence is not independently verified.');return;
    }
    if (form.dataset.form==='video') {
      if (data.source==='upload') {
        const upload=new FormData(form);const file=upload.get('file');
        if(!file?.size) throw new Error('Choose a video file first.');
        const allowed=['video/mp4','video/webm','video/quicktime'];
        if(!allowed.includes(file.type)) throw new Error('Choose an MP4, WebM or MOV video.');
        const config=await api('/api/config');
        if(config.upload_mode==='link-only') throw new Error('Video uploads are not configured yet. Use a secure video URL instead.');
        if(file.size>config.max_video_bytes) throw new Error(`Video exceeds the ${Math.round(config.max_video_bytes/1024/1024)} MB upload limit.`);
        if(config.upload_mode==='cloud') {
          if(submit) submit.textContent='Uploading to secure video storage…';
          const signed=await api('/api/videos/sign-upload',{method:'POST',body:{visibility:data.visibility}});
          const cloudBody=new FormData();
          cloudBody.append('file',file);
          for(const key of ['api_key','timestamp','public_id','type','signature']) cloudBody.append(key,signed[key]);
          const cloudResponse=await fetch(`https://api.cloudinary.com/v1_1/${encodeURIComponent(signed.cloud_name)}/video/upload`,{method:'POST',body:cloudBody});
          const cloudAsset=await cloudResponse.json().catch(()=>({}));
          if(!cloudResponse.ok) throw new Error(cloudAsset.error?.message || 'Cloud video upload failed. Retry in a moment.');
          await api('/api/videos/complete-upload',{method:'POST',body:{ticket:signed.ticket,title:data.title,kind:data.kind,asset:{public_id:cloudAsset.public_id,version:cloudAsset.version,signature:cloudAsset.signature,resource_type:cloudAsset.resource_type,type:cloudAsset.type,format:cloudAsset.format,bytes:cloudAsset.bytes}}});
        } else {
          const body=new FormData();['title','kind','visibility'].forEach(k=>body.append(k,data[k]));body.append('file',file);
          await api('/api/videos/upload',{method:'POST',body,form:true});
        }
      } else {if(!data.url)throw new Error('Paste your video URL.');await api('/api/videos/link',{method:'POST',body:{title:data.title,kind:data.kind,visibility:data.visibility,url:data.url}});}
      closeModal();await fetchMyData();await fetchAll();toast('Footage added to your portfolio.');return;
    }
    if (form.dataset.form==='tournament') {
      await api('/api/tournaments',{method:'POST',body:{title:data.title,sport:data.sport,location:data.location,level:data.level,capacity:Number(data.capacity),start_date:data.start_date,end_date:data.end_date,registration_deadline:data.registration_deadline,description:data.description}});
      closeModal();state.activeStatus='upcoming';await fetchAll();toast('Tournament published. Players can now discover it.');$('#tournaments').scrollIntoView({behavior:'smooth'});return;
    }
    if (form.dataset.form==='evaluate') {
      const payload = {technique:Number(data.technique),teamwork:Number(data.teamwork),consistency:Number(data.consistency),potential:Number(data.potential),notes:data.notes};
      await api(`/api/scouting/${form.dataset.id}/evaluate`,{method:'POST',body:payload});closeModal();await fetchMyData();toast('Assessment saved privately.');return;
    }
  } catch(error) {toast(error.message,true);} finally {if(submit){submit.disabled=false;submit.textContent=originalSubmitText;}}
}
function setupEvents() {
  document.addEventListener('click',(event)=>{
    const control=event.target.closest('[data-action]');
    if(control) {event.preventDefault();runAction(control.dataset.action,control.dataset.id);}
    const tab=event.target.closest('[data-tab]');if(tab){state.activeStatus=tab.dataset.tab;renderTournaments();}
    const nav=event.target.closest('[data-nav-link]');if(nav){$('#main-nav').classList.remove('open');$('#mobile-menu').setAttribute('aria-expanded','false');}
  });
  document.addEventListener('submit',(event)=>{if(event.target.matches('[data-form]')){event.preventDefault();submitForm(event.target);}});
  $('#player-search').addEventListener('input',renderPlayers);
  $('#player-sport').addEventListener('change',renderPlayers);
  $('#tournament-sport').addEventListener('change',renderTournaments);
  $('#mobile-menu').addEventListener('click',()=>{const open=$('#main-nav').classList.toggle('open');$('#mobile-menu').setAttribute('aria-expanded',String(open));});
  document.addEventListener('change',(event)=>{
    if(event.target.name==='source'){$('#video-link-group').hidden=event.target.value!=='link';$('#video-upload-group').hidden=event.target.value!=='upload';}
  });
  document.addEventListener('keydown',(event)=>{
    if(event.key==='Escape'&&!$('#modal-shell').hidden)closeModal();
    if(event.key==='Tab'&&!$('#modal-shell').hidden){const focusable=$$('button:not(:disabled),a[href],input:not(:disabled),select:not(:disabled),textarea:not(:disabled)', $('#modal-window')).filter(el=>el.getClientRects().length);if(!focusable.length)return;const first=focusable[0],last=focusable.at(-1);if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}}
  });
}
function setupAnimations() {
  if(!('IntersectionObserver' in window) || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const observer=new IntersectionObserver((entries)=>{for(const entry of entries){if(entry.isIntersecting){entry.target.classList.remove('will-reveal');entry.target.classList.add('is-visible');observer.unobserve(entry.target);}}},{threshold:.12});
  $$('.reveal').forEach(el=>{el.classList.add('will-reveal');observer.observe(el);});
}
async function init() {
  $('#year').textContent=new Date().getFullYear();setupEvents();setupAnimations();
  if(state.token){try{state.user=await api('/api/auth/me');}catch{state.token='';sessionStorage.removeItem('ps_token');}}
  renderNav();updateWorkspace();await fetchAll();
}
init().catch((error)=>toast(error.message,true));
