/* default_prophylactic_debroeslar — v2 three-layer-aware
 * 2026-05-22 — operator: maintainer@example.com
 *
 * Implements the three-layer storage doctrine:
 *
 *   Layer 1 — HTTP cookies:  DEPRECATED-VOID. Zero. Sweep + ALARM on any.
 *   Layer 2 — Client-state:  Transparent + minimal + function-bound.
 *                             v0.1.2 whitelist (post URL-state migration):
 *                               localStorage:   (empty)
 *                               sessionStorage: (empty)
 *                               IndexedDB:      (empty in v0.1.x)
 *                             v0.2 will add: IndexedDB[{{YOUR_PROJECT_NAME}}-local-chats,
 *                                            {{YOUR_PROJECT_NAME}}-favorites] for opt-in archive.
 *                             Anything outside whitelist → sweep + ALARM.
 *   Layer 3 — Server-state:  Zero-by-default (Option A v0.2).
 *                             Not browser-observable from here.
 *
 * Visible UI:
 *   🟢 bottom-right dim dot when storage matches whitelist.
 *   🔴 pulsing dot + red ALARM banner when anything outside whitelist found.
 *   Hover/focus the dot → tooltip with layered scan summary.
 *
 * Doctrine refs:
 *   bröselfrei-2026-decree (cookie=deprecated-void)
 *   three-layer-storage-doctrine
 *   audit-open-door-doctrine (proof-of-work made visible)
 *   propaganda-over-ransomware (observable state = untrusted; we verify, not declare)
 */
(function(){
  'use strict';

  // ─── Whitelist policy (function-bound, declared) ─────────────────────
  var WHITELIST = {
    localStorage:   new Set(),                  // EMPTY (v0.1.2 — theme migrated to URL search-param)
    sessionStorage: new Set(),                  // empty — no use-case identified
    indexedDB:      new Set()                   // empty in v0.1.x; v0.2 adds user-archive
  };

  var BADGE_ID = 'default_prophylactic_debroeslar_badge';
  var ALARM_ID = 'default_prophylactic_debroeslar_alarm';

  function nowIso(){
    return new Date().toISOString().slice(11, 19) + 'Z';
  }

  // ─── Scanners (each returns {found: [...keys], unauthorized: [...keys]}) ──
  function scanCookies(){
    var raw = document.cookie || '';
    if(!raw.trim()) return {found: [], unauthorized: []};
    var names = raw.split(';')
      .map(function(s){ return s.trim().split('=')[0]; })
      .filter(function(n){ return n.length > 0; });
    return {found: names, unauthorized: names};  // ALL cookies are unauthorized
  }

  function scanStorage(store, whitelist){
    var found = [];
    var unauthorized = [];
    try{
      for(var i = 0; i < store.length; i++){
        var k = store.key(i);
        if(k === null) continue;
        found.push(k);
        if(!whitelist.has(k)) unauthorized.push(k);
      }
    }catch(_){}
    return {found: found, unauthorized: unauthorized};
  }

  function scanIndexedDB(whitelist){
    // indexedDB.databases() is Promise-based and not available everywhere.
    if(!window.indexedDB || typeof indexedDB.databases !== 'function'){
      return Promise.resolve({found: [], unauthorized: [], note: 'unsupported-browser-api'});
    }
    return indexedDB.databases().then(function(dbs){
      var names = dbs.map(function(d){ return d.name; }).filter(Boolean);
      var unauthorized = names.filter(function(n){ return !whitelist.has(n); });
      return {found: names, unauthorized: unauthorized};
    }).catch(function(){
      return {found: [], unauthorized: [], note: 'scan-failed'};
    });
  }

  function sweepIndexedDB(names){
    // Best-effort delete of each named database. Returns Promise that resolves
    // when all attempts have completed (regardless of individual success).
    if(!window.indexedDB || names.length === 0){
      return Promise.resolve([]);
    }
    var attempts = names.map(function(name){
      return new Promise(function(resolve){
        try{
          var req = indexedDB.deleteDatabase(name);
          req.onsuccess = function(){ resolve({name: name, status: 'deleted'}); };
          req.onerror   = function(){ resolve({name: name, status: 'error'}); };
          req.onblocked = function(){ resolve({name: name, status: 'blocked'}); };
        }catch(e){
          resolve({name: name, status: 'exception'});
        }
      });
    });
    return Promise.all(attempts);
  }

  // ─── Sweepers ────────────────────────────────────────────────────────
  function sweepCookies(names){
    var host = location.hostname;
    var domains = ['', host];
    var parts = host.split('.');
    while(parts.length > 1){
      domains.push('.' + parts.join('.'));
      parts.shift();
    }
    var paths = ['/', '/cc', '/cc/api', '/api', location.pathname || '/'];
    names.forEach(function(name){
      paths.forEach(function(p){
        domains.forEach(function(d){
          var attr = 'expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0; path=' + p;
          if(d) attr += '; domain=' + d;
          document.cookie = name + '=; ' + attr;
        });
      });
    });
  }

  function sweepStorageKeys(store, keys){
    keys.forEach(function(k){
      try{ store.removeItem(k); }catch(_){}
    });
  }

  // ─── Badge + tooltip rendering ───────────────────────────────────────
  function ensureBadge(){
    var existing = document.getElementById(BADGE_ID);
    if(existing) return existing;

    var badge = document.createElement('div');
    badge.id = BADGE_ID;
    badge.setAttribute('role', 'status');
    badge.setAttribute('aria-label', 'debroeslar storage audit status');
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
    tooltip.id = BADGE_ID + '_tooltip';
    tooltip.style.cssText = [
      'position:absolute','bottom:160%','right:0',
      'min-width:290px','max-width:360px',
      'padding:.6rem .8rem',
      'background:rgba(14,19,32,.97)','color:#e8eef5',
      'border:1px solid rgba(255,255,255,.18)','border-radius:5px',
      'font:11px ui-monospace,Menlo,Consolas,monospace',
      'line-height:1.55','letter-spacing:.01em',
      'box-shadow:0 6px 22px rgba(0,0,0,.5)',
      'opacity:0','pointer-events:none','transition:opacity .2s',
      'text-align:left','white-space:normal'
    ].join(';');
    badge.appendChild(tooltip);

    function showTip(){
      tooltip.style.opacity = '1';
      badge.style.opacity = '1';
      badge.style.transform = 'scale(1.15)';
    }
    function hideTip(){
      tooltip.style.opacity = '0';
      if(!badge.classList.contains('debroeslar-alarm')){
        badge.style.opacity = '.45';
        badge.style.transform = 'scale(1)';
      }
    }
    badge.addEventListener('mouseenter', showTip);
    badge.addEventListener('mouseleave', hideTip);
    badge.addEventListener('focus', showTip);
    badge.addEventListener('blur', hideTip);

    if(document.body) document.body.appendChild(badge);
    else document.addEventListener('DOMContentLoaded', function(){ document.body.appendChild(badge); }, {once:true});
    return badge;
  }

  function setBadgeState(badge, alarm){
    if(alarm){
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
    } else {
      badge.classList.remove('debroeslar-alarm');
      badge.style.background = '#3fa850';
      badge.style.boxShadow = '0 0 5px rgba(63,168,80,.45)';
      badge.style.opacity = '.45';
      badge.style.animation = '';
    }
  }

  function escHtml(s){
    return String(s).replace(/[<>&"'`]/g, function(c){
      return ({'<':'&lt;','>':'&gt;','&':'&amp;','"':'&quot;',"'":'&#39;','`':'&#96;'})[c];
    });
  }

  function fmtKeys(keys, maxShow){
    if(keys.length === 0) return '';
    var shown = keys.slice(0, maxShow).map(escHtml).join(', ');
    var rest = keys.length > maxShow ? ' +' + (keys.length - maxShow) + ' more' : '';
    return shown + rest;
  }

  function renderTooltip(badge, scan){
    var tt = badge.querySelector('div');
    if(!tt) return;

    var hasAlarm = scan.cookies.unauthorized.length > 0
                 || scan.localStorage.unauthorized.length > 0
                 || scan.sessionStorage.unauthorized.length > 0
                 || scan.indexedDB.unauthorized.length > 0;

    var headerColor = hasAlarm ? '#c0292c' : '#3fa850';
    var headerText  = hasAlarm ? '🚨 unauthorized storage found' : '🟢 storage transparent';

    var rows = [
      '<div style="color:' + headerColor + ';font-weight:600;letter-spacing:.04em">' + headerText + '</div>',
      '<div style="color:#8b96a6;margin:.3rem 0 .45rem">default_prophylactic_debroeslar v2 · three-layer doctrine</div>'
    ];

    // Layer 1
    rows.push('<div style="margin-top:.2rem">');
    rows.push('<div style="color:#8b96a6;font-size:10px;letter-spacing:.06em">LAYER 1 — HTTP cookies (deprecated-void)</div>');
    if(scan.cookies.found.length === 0){
      rows.push('<div>✓ 0 cookies</div>');
    } else {
      rows.push('<div style="color:#c0292c">✗ ' + scan.cookies.found.length + ' cookie(s) found + swept: <span style="word-break:break-all">' + fmtKeys(scan.cookies.found, 4) + '</span></div>');
    }
    rows.push('</div>');

    // Layer 2
    rows.push('<div style="margin-top:.45rem">');
    rows.push('<div style="color:#8b96a6;font-size:10px;letter-spacing:.06em">LAYER 2 — client-state (transparent + minimal)</div>');

    // localStorage
    if(scan.localStorage.unauthorized.length === 0){
      var lsOK = scan.localStorage.found.length;
      rows.push('<div>' + (lsOK === 0 ? '✓ localStorage: 0' :
                  '✓ localStorage: ' + lsOK + ' (whitelisted: ' + fmtKeys(scan.localStorage.found, 3) + ')') + '</div>');
    } else {
      rows.push('<div style="color:#c0292c">✗ localStorage unauthorized: ' + fmtKeys(scan.localStorage.unauthorized, 3) + '</div>');
    }
    // sessionStorage
    if(scan.sessionStorage.unauthorized.length === 0){
      rows.push('<div>✓ sessionStorage: ' + scan.sessionStorage.found.length + '</div>');
    } else {
      rows.push('<div style="color:#c0292c">✗ sessionStorage unauthorized: ' + fmtKeys(scan.sessionStorage.unauthorized, 3) + '</div>');
    }
    // IndexedDB
    if(scan.indexedDB.note === 'unsupported-browser-api'){
      rows.push('<div style="color:#8b96a6">~ IndexedDB: scan unsupported in this browser</div>');
    } else if(scan.indexedDB.unauthorized.length === 0){
      rows.push('<div>✓ IndexedDB: ' + scan.indexedDB.found.length + '</div>');
    } else {
      rows.push('<div style="color:#c0292c">✗ IndexedDB unauthorized: ' + fmtKeys(scan.indexedDB.unauthorized, 3) + '</div>');
    }
    rows.push('</div>');

    // Layer 3
    rows.push('<div style="margin-top:.45rem">');
    rows.push('<div style="color:#8b96a6;font-size:10px;letter-spacing:.06em">LAYER 3 — server-state</div>');
    rows.push('<div style="color:#8b96a6">Zero-by-default planned (v0.2). Not browser-observable here.</div>');
    rows.push('</div>');

    rows.push('<div style="color:#8b96a6;font-size:10px;margin-top:.5rem">Last scan: ' + nowIso() + '</div>');
    rows.push('<div style="margin-top:.4rem;padding-top:.35rem;border-top:1px solid rgba(255,255,255,.1)">');
    rows.push('<a href="/default_prophylactic_debroeslar.js" target="_blank" rel="noopener" style="color:#58a6ff;text-decoration:none">view source</a> · ');
    rows.push('<a href="/datenschutz.html#cookies" style="color:#58a6ff;text-decoration:none">Datenschutz</a>');
    if(hasAlarm){
      rows.push(' · <a href="https://{{YOUR_CODEBERG_REPO}}/issues" target="_blank" rel="noopener" style="color:#58a6ff;text-decoration:none">report</a>');
    }
    rows.push('</div>');

    tt.innerHTML = rows.join('');
  }

  function showAlarmBanner(allUnauthorized){
    if(document.getElementById(ALARM_ID)) return;
    if(allUnauthorized.length === 0) return;
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
      'unauthorized storage gefunden + ausgekehrt: ' +
      '<code style="background:rgba(255,255,255,.18);padding:.1rem .4rem;border-radius:3px;font-family:inherit">' +
      allUnauthorized.map(escHtml).join(', ') +
      '</code> &mdash; bitte melden: ' +
      '<a href="https://{{YOUR_CODEBERG_REPO}}/issues" ' +
      'target="_blank" rel="noopener" ' +
      'style="color:#fff;text-decoration:underline;font-weight:700">Issue-Tracker</a>';
    if(document.body) document.body.insertBefore(banner, document.body.firstChild);
    else document.addEventListener('DOMContentLoaded', function(){ document.body.insertBefore(banner, document.body.firstChild); }, {once:true});
  }

  // ─── Orchestration ───────────────────────────────────────────────────
  function run(){
    var badge = ensureBadge();

    var scan = {
      cookies:        scanCookies(),
      localStorage:   {found: [], unauthorized: []},
      sessionStorage: {found: [], unauthorized: []},
      indexedDB:      {found: [], unauthorized: []}
    };

    // Cookies — sweep all (deprecated-void)
    if(scan.cookies.unauthorized.length > 0){
      sweepCookies(scan.cookies.unauthorized);
    }

    // localStorage
    try{
      if(window.localStorage){
        scan.localStorage = scanStorage(localStorage, WHITELIST.localStorage);
        if(scan.localStorage.unauthorized.length > 0){
          sweepStorageKeys(localStorage, scan.localStorage.unauthorized);
        }
      }
    }catch(_){}

    // sessionStorage
    try{
      if(window.sessionStorage){
        scan.sessionStorage = scanStorage(sessionStorage, WHITELIST.sessionStorage);
        if(scan.sessionStorage.unauthorized.length > 0){
          sweepStorageKeys(sessionStorage, scan.sessionStorage.unauthorized);
        }
      }
    }catch(_){}

    // First render with what we have synchronously
    renderTooltip(badge, scan);

    var allUnauthorized =
      scan.cookies.unauthorized
        .concat(scan.localStorage.unauthorized)
        .concat(scan.sessionStorage.unauthorized);

    if(allUnauthorized.length > 0){
      setBadgeState(badge, true);
      showAlarmBanner(allUnauthorized);
      if(window.console && console.warn){
        console.warn('[default_prophylactic_debroeslar] unauthorized storage on ' + location.hostname + ':', allUnauthorized);
      }
    } else {
      setBadgeState(badge, false);
    }

    // IndexedDB scan + sweep (async). v0.1.x whitelist is empty, so any IDB
    // database on the origin is unauthorized → swept. v0.2 will whitelist
    // {{YOUR_PROJECT_NAME}}-local-chats + {{YOUR_PROJECT_NAME}}-favorites for the opt-in user archive.
    scanIndexedDB(WHITELIST.indexedDB).then(function(idbResult){
      scan.indexedDB = idbResult;
      var idbUnauthorized = idbResult.unauthorized || [];
      if(idbUnauthorized.length === 0){
        renderTooltip(badge, scan);
        return;
      }
      // Surface alarm immediately with the found names — sweep follows async
      setBadgeState(badge, true);
      showAlarmBanner(idbUnauthorized);
      if(window.console && console.warn){
        console.warn('[default_prophylactic_debroeslar] unauthorized IndexedDB databases (sweeping):', idbUnauthorized);
      }
      renderTooltip(badge, scan);
      sweepIndexedDB(idbUnauthorized).then(function(results){
        if(window.console && console.info){
          console.info('[default_prophylactic_debroeslar] IndexedDB sweep results:', results);
        }
        // Re-scan to refresh tooltip with post-sweep truth
        scanIndexedDB(WHITELIST.indexedDB).then(function(after){
          scan.indexedDB = after;
          renderTooltip(badge, scan);
          // Clear alarm if everything else is also clean now
          if((after.unauthorized||[]).length === 0
             && scan.cookies.unauthorized.length === 0
             && scan.localStorage.unauthorized.length === 0
             && scan.sessionStorage.unauthorized.length === 0){
            setBadgeState(badge, false);
            var existingBanner = document.getElementById(ALARM_ID);
            if(existingBanner && existingBanner.parentNode){
              existingBanner.parentNode.removeChild(existingBanner);
            }
          }
        });
      });
    });
  }

  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', run, {once:true});
  } else {
    run();
  }
})();
