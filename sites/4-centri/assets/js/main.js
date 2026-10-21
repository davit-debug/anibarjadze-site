/* nav, events, form (as site 3) + routing: ?r=<value>, form[data-routing], a[data-route] -> #f-routing */
(function(){
var d=document,body=d.body,sel=d.getElementById('f-routing');
function exp(el,o){el.setAttribute('aria-expanded',!!o);}
function isOpen(el){return el.getAttribute('aria-expanded')==='true';}
function track(n){if(typeof window.plausible==='function')window.plausible(n,{props:{page:location.pathname}});}
function route(v){if(sel&&v&&sel.querySelector('option[value="'+v+'"]'))sel.value=v;}
d.querySelectorAll('form[data-routing]').forEach(function(f){route(f.getAttribute('data-routing'));});
route(new URLSearchParams(location.search).get('r'));

var toggle=d.querySelector('.nav-toggle'),nav=d.getElementById('site-nav');
function setMenu(o){
if(!toggle)return;
exp(toggle,o);nav.classList.toggle('is-open',o);body.classList.toggle('nav-open',o);
}
if(toggle&&nav)toggle.addEventListener('click',function(){setMenu(!isOpen(toggle));});

var groups=d.querySelectorAll('.nav-group__btn');
function closeGroups(x){groups.forEach(function(b){if(b!==x)exp(b,false);});}
groups.forEach(function(b){b.addEventListener('click',function(){closeGroups(b);exp(b,!isOpen(b));});});

d.addEventListener('keydown',function(e){
if(e.key!=='Escape')return;
var g=d.activeElement.closest('.nav-group');
closeGroups();
if(g)g.firstElementChild.focus();
else if(toggle&&isOpen(toggle)){setMenu(false);toggle.focus();}
});

function out(e){if(!e.target.closest('.nav-group'))closeGroups();}
d.addEventListener('focusin',out);
d.addEventListener('click',function(e){
var t=e.target,a=t.closest('a[data-route]'),el=t.closest('[data-event]');
out(e);
if(a&&sel&&a.pathname===location.pathname){e.preventDefault();route(a.getAttribute('data-route'));location.hash='forma';}
if(el&&el.getAttribute('data-event')!=='form_submit')track(el.getAttribute('data-event'));
});

d.addEventListener('toggle',function(e){
if(e.target.matches&&e.target.matches('details.faq'))body.classList.toggle('faq-open',!!d.querySelector('details.faq[open]'));
},true);

d.querySelectorAll('form[data-ajax]').forEach(function(f){
var btn=f.querySelector('[type=submit]'),st=f.querySelector('.form__status');
function msg(c,s){st.className='form__status'+c;st.textContent=s;}
f.addEventListener('submit',function(e){
e.preventDefault();
if(f.hasAttribute('data-demo'))return msg('','დემო-რეჟიმში ფორმა არ იგზავნება');
if(btn.disabled)return;
btn.disabled=true;
f.setAttribute('aria-busy','true');
msg('',f.getAttribute('data-msg-sending'));
fetch(f.action,{method:'POST',body:new FormData(f),headers:{Accept:'application/json'}})
.then(function(r){return r.json().catch(function(){return {};}).then(function(j){if(!r.ok||!j.ok)throw {m:j.error};});})
.then(function(){msg(' is-ok',f.getAttribute('data-msg-ok'));f.reset();track('form_submit');})
.catch(function(err){msg(' is-err',(err&&err.m)||f.getAttribute('data-msg-err'));})
.then(function(){btn.disabled=false;f.removeAttribute('aria-busy');});
});
});
})();
