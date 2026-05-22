/* default_prophylactic_debroeslar
 * 2026-05-22 — operator: bsr@bayaman.de
 *
 * Prophylactic cookie sweeper for vectoryz-Liegenschaft.
 * Runs on every page-load. Detects any HTTP cookie present on this origin
 * (there should be zero per the bröselfrei-2026-decree), sweeps it across
 * plausible path/domain combinations, and surfaces a visible status badge:
 *
 *   🟢 (dim, bottom-right) — clean. Hover for scan details.
 *   🔴 (pulsing) + red ALARM banner — cookies found. Hover for which ones.
 *
 * Symmetric audit-open-door: declare bröselfrei AND show the scan ran.
 * Proof-of-work made visible. Honesty before silence is doctrine.
 *
 * Related doctrine:
 *   bröselfrei-2026-decree, audit-open-door-doctrine, propaganda-over-ransomware.
 */
(function(){
  'use strict';

  var BADGE_ID = 'default_prophylactic_debroeslar_badge';
  var ALARM_ID = 'default_prophylactic_debroeslar_alarm';

  function nowIso(){
    return new Date().toISOString().slice(11, 19) + 'Z';
  }

  function ensureBadge(){
    var existing = document.getElementById(BADGE_ID);
    if(existing) return existing;
    var badge = document.createElement('div');
    badge.id = BADGE_ID;
    badge.setAttribute('role', 'status');
    badge.setAttribute('aria-label', 'debroeslar audit status');
    badge.setAttribute('tabindex', '0');
    badge.style.cssText = [
      'position:fixed','bottom:.5rem','right:.5rem',
      'z-index:2147483646',
      'width:.7em','height:.7em','font-size:14px',
      'border-radius:50%',
      'background:#3fa850',
      'box-shadow:0 0 5px rgba(63,168,80,.45)',
      'opacity:.45','cursor:help',
      'transition:opacity .18s,transform .18s,background .25s,box-shadow .25s'
    ].join(';');

    var tooltip = document.createElement('div');
    tooltip.style.cssText = [
      'position:absolute','bottom:160%','right:0',
      'min-width:260px','max-width:320px',
      'padding:.55rem .75rem',
      'background:rgba(14,19,32,.96)','color:#e8eef5',
      'border:1px solid rgba(255,255,255,.15)','border-radius:5px',
      'font:11px ui-monospace,Menlo,Consolas,monospace',
      'line-height:1.55','letter-spacing:.01em',
      'box-shadow:0 6px 20px rgba(0,0,0,.45)',
      'opacity:0','pointer-events:none','transition:opacity .2s',
      'text-align:left'
    ].join(';');
    tooltip.id = BADGE_ID + '_tooltip';
    badge.appendChild(tooltip);

    function showTip(){ tooltip.style.opacity = '1'; badge.style.opacity = '1'; badge.style.transform = 'scale(1.15)'; }
    function hideTip(){ tooltip.style.opacity = '0'; if(!badge.classList.contains('debroeslar-alarm')){ badge.style.opacity = '.45'; badge.style.transform = 'scale(1)'; } }
    badge.addEventListener('mouseenter', showTip);
    badge.addEventListener('mouseleave', hideTip);
    badge.addEventListener('focus', showTip);
    badge.addEventListener('blur', hideTip);

    var attach = function(){
      if(document.body) document.body.appendChild(badge);
      else document.addEventListener('DOMContentLoaded', function(){ document.body.appendChild(badge); }, {once:true});
    };
    attach();
    return badge;
  }

  function renderCleanTooltip(badge){
    var tt = badge.querySelector('div');
    if(!tt) return;
    tt.innerHTML =
      '<div style="color:#3fa850;font-weight:600;letter-spacing:.04em">🟢 bröselfrei</div>' +
      '<div style="color:#8b96a6;margin:.3rem 0 .35rem">default_prophylactic_debroeslar v1</div>' +
      '<div>✓ HTTP cookies: <strong>0</strong></div>' +
      '<div>✓ Set-Cookie response: <strong>none</strong></div>' +
      '<div style="color:#8b96a6;font-size:10px;margin-top:.35rem">Last scan: ' + nowIso() + '</div>' +
      '<div style="margin-top:.4rem;padding-top:.35rem;border-top:1px solid rgba(255,255,255,.08)">' +
      '<a href="/default_prophylactic_debroeslar.js" target="_blank" rel="noopener" style="color:#58a6ff;text-decoration:none">view source</a> · ' +
      '<a href="/datenschutz.html#cookies" style="color:#58a6ff;text-decoration:none">Datenschutz</a>' +
      '</div>';
  }

  function renderAlarmTooltip(badge, names){
    var tt = badge.querySelector('div');
    if(!tt) return;
    var safe = names.map(function(n){ return n.replace(/[<>&"'`]/g, '?'); });
    tt.innerHTML =
      '<div style="color:#c0292c;font-weight:600;letter-spacing:.04em">🚨 ALARM — cookies found</div>' +
      '<div style="color:#8b96a6;margin:.3rem 0 .35rem">default_prophylactic_debroeslar v1</div>' +
      '<div>Cookies swept: <strong>' + safe.length + '</strong></div>' +
      '<div style="color:#c0292c;margin-top:.2rem;font-size:10px;word-break:break-all">' +
      safe.join(', ') + '</div>' +
      '<div style="color:#8b96a6;font-size:10px;margin-top:.35rem">Last scan: ' + nowIso() + '</div>' +
      '<div style="margin-top:.4rem;padding-top:.35rem;border-top:1px solid rgba(255,255,255,.08)">' +
      'Bitte melden: <a href="https://codeberg.org/vxctxryz/vectoryz/issues" style="color:#58a6ff;text-decoration:none">Issue-Tracker</a>' +
      '</div>';
  }

  function setBadgeAlarm(badge){
    badge.classList.add('debroeslar-alarm');
    badge.style.background = '#c0292c';
    badge.style.boxShadow = '0 0 8px rgba(192,41,44,.7)';
    badge.style.opacity = '1';
    badge.style.animation = 'debroeslar-pulse 1.2s ease-in-out infinite';
    if(!document.getElementById('debroeslar-keyframes')){
      var st = document.createElement('style');
      st.id = 'debroeslar-keyframes';
      st.textContent = '@keyframes debroeslar-pulse{0%,100%{transform:scale(1)}50%{transform:scale(1.3)}}';
      document.head.appendChild(st);
    }
  }

  function showAlarmBanner(safeNames){
    if(document.getElementById(ALARM_ID)) return;
    var banner = document.createElement('div');
    banner.id = ALARM_ID;
    banner.setAttribute('role','alert');
    banner.style.cssText = [
      'position:fixed','top:0','left:0','right:0',
      'z-index:2147483647',
      'background:#c0292c','color:#fff',
      'padding:.7rem 1rem',
      'font:600 13px ui-monospace,Menlo,Consolas,monospace',
      'text-align:center',
      'box-shadow:0 2px 12px rgba(192,41,44,.6)',
      'border-bottom:2px solid #fff',
      'letter-spacing:.01em'
    ].join(';');
    banner.innerHTML =
      '\u{1F6A8} default_prophylactic_debroeslar ALARM &mdash; ' +
      'unerwartete Cookie(s) gefunden + ausgekehrt: ' +
      '<code style="background:rgba(255,255,255,.18);padding:.1rem .4rem;border-radius:3px;font-family:inherit">' +
      safeNames.join(', ') +
      '</code> &mdash; bitte melden: ' +
      '<a href="https://codeberg.org/vxctxryz/vectoryz/issues" ' +
      'style="color:#fff;text-decoration:underline;font-weight:700">Issue-Tracker</a>';
    if(document.body) document.body.insertBefore(banner, document.body.firstChild);
    else document.addEventListener('DOMContentLoaded', function(){ document.body.insertBefore(banner, document.body.firstChild); }, {once:true});
  }

  function run(){
    var badge = ensureBadge();

    try{
      var raw = document.cookie || '';
      var found = raw.trim()
        ? raw.split(';').map(function(s){ return s.trim().split('=')[0]; }).filter(function(n){ return n.length > 0; })
        : [];

      if(found.length === 0){
        renderCleanTooltip(badge);
        return;
      }

      var host = location.hostname;
      var domains = ['', host];
      var parts = host.split('.');
      while(parts.length > 1){
        domains.push('.' + parts.join('.'));
        parts.shift();
      }
      var paths = ['/', '/cc', '/cc/api', '/api', location.pathname || '/'];
      found.forEach(function(name){
        paths.forEach(function(p){
          domains.forEach(function(d){
            var attr = 'expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0; path=' + p;
            if(d) attr += '; domain=' + d;
            document.cookie = name + '=; ' + attr;
          });
        });
      });

      var safe = found.map(function(n){ return n.replace(/[<>&"'`]/g, '?'); });
      setBadgeAlarm(badge);
      renderAlarmTooltip(badge, found);
      showAlarmBanner(safe);

      if(window.console && console.warn){
        console.warn('[default_prophylactic_debroeslar] unexpected cookies on ' + host + ':', found);
      }
    }catch(e){
      if(window.console && console.error){
        console.error('[default_prophylactic_debroeslar] internal error:', e);
      }
      // Even on internal error: render badge so user knows scan attempted
      try{ renderCleanTooltip(badge); }catch(_){}
    }
  }

  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', run, {once:true});
  } else {
    run();
  }
})();
