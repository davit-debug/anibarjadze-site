/* nav, events, form (data-demo: no send) */
(function () {
 var d = document, body = d.body;
 function exp(el, open) { el.setAttribute('aria-expanded', open ? 'true' : 'false'); }
 function isOpen(el) { return el.getAttribute('aria-expanded') === 'true'; }
 function track(name) {
  if (typeof window.plausible === 'function') window.plausible(name, { props: { page: location.pathname } });
 }

 var toggle = d.querySelector('.nav-toggle'), nav = d.getElementById('site-nav');
 function setMenu(open) {
  if (!toggle) return;
  exp(toggle, open);
  nav.classList.toggle('is-open', open);
  body.classList.toggle('nav-open', open);
 }
 if (toggle && nav) toggle.addEventListener('click', function () { setMenu(!isOpen(toggle)); });

 var groups = d.querySelectorAll('.nav-group__btn');
 function closeGroups(except) {
  groups.forEach(function (b) { if (b !== except) exp(b, false); });
 }
 groups.forEach(function (b) {
  b.addEventListener('click', function () { closeGroups(b); exp(b, !isOpen(b)); });
 });

 d.addEventListener('keydown', function (e) {
  if (e.key !== 'Escape') return;
  var g = d.activeElement.closest('.nav-group');
  closeGroups();
  if (g) g.firstElementChild.focus();
  else if (toggle && isOpen(toggle)) { setMenu(false); toggle.focus(); }
 });

 function out(e) { if (!e.target.closest('.nav-group')) closeGroups(); }
 d.addEventListener('focusin', out);
 d.addEventListener('click', function (e) {
  var t = e.target;
  out(e);
  var el = t.closest('[data-event]');
  if (el && el.getAttribute('data-event') !== 'form_submit') track(el.getAttribute('data-event'));
 });

 d.addEventListener('toggle', function (e) {
  if (e.target.matches && e.target.matches('details.faq')) {
   body.classList.toggle('faq-open', !!d.querySelector('details.faq[open]'));
  }
 }, true);

 d.querySelectorAll('form[data-ajax]').forEach(function (f) {
  var btn = f.querySelector('[type=submit]'), st = f.querySelector('.form__status');
  f.addEventListener('submit', function (e) {
   e.preventDefault();
   if (f.hasAttribute('data-demo')) { st.textContent = 'დემო-რეჟიმში ფორმა არ იგზავნება'; return; }
   if (btn.disabled) return;
   btn.disabled = true;
   f.setAttribute('aria-busy', 'true');
   st.className = 'form__status';
   st.textContent = f.getAttribute('data-msg-sending');
   fetch(f.action, { method: 'POST', body: new FormData(f), headers: { Accept: 'application/json' } })
    .then(function (r) {
     return r.json().catch(function () { return {}; }).then(function (j) {
      if (!r.ok || !j.ok) throw { m: j.error };
     });
    })
    .then(function () {
     st.className = 'form__status is-ok';
     st.textContent = f.getAttribute('data-msg-ok');
     f.reset();
     track('form_submit');
    })
    .catch(function (err) {
     st.className = 'form__status is-err';
     st.textContent = (err && err.m) || f.getAttribute('data-msg-err');
    })
    .then(function () {
     btn.disabled = false;
     f.removeAttribute('aria-busy');
    });
  });
 });
})();
