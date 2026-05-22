/* default_prophylactic_debroeslar
 * 2026-05-22 — operator: bsr@bayaman.de
 *
 * Prophylactic cookie sweeper for vectoryz-Liegenschaft.
 * Runs on every page-load. Detects any HTTP cookie present on this origin
 * (there should be zero per the bröselfrei-2026-decree), sweeps it across
 * plausible path/domain combinations, and — if any were found — surfaces
 * a red ALARM banner. Honesty before silence is doctrine, not feature.
 *
 * Related doctrine:
 *   bröselfrei-2026-decree, audit-open-door-doctrine, propaganda-over-ransomware.
 */
(function(){
  'use strict';
  try{
    var raw = document.cookie || '';
    if(!raw.trim()) return;

    var found = raw.split(';')
      .map(function(s){ return s.trim().split('=')[0]; })
      .filter(function(n){ return n.length > 0; });
    if(found.length === 0) return;

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

    var safe = found.map(function(n){
      return n.replace(/[<>&"'`]/g, '?');
    }).join(', ');

    var insert = function(){
      if(!document.body) return;
      if(document.getElementById('default_prophylactic_debroeslar_alarm')) return;
      var banner = document.createElement('div');
      banner.id = 'default_prophylactic_debroeslar_alarm';
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
        safe +
        '</code> &mdash; bitte melden: ' +
        '<a href="https://codeberg.org/vxctxryz/vectoryz/issues" ' +
        'style="color:#fff;text-decoration:underline;font-weight:700">Issue-Tracker</a>';
      document.body.insertBefore(banner, document.body.firstChild);
    };

    if(document.body) insert();
    else document.addEventListener('DOMContentLoaded', insert);

    if(window.console && console.warn){
      console.warn('[default_prophylactic_debroeslar] unexpected cookies on ' + host + ':', found);
    }
  }catch(e){
    if(window.console && console.error){
      console.error('[default_prophylactic_debroeslar] internal error:', e);
    }
  }
})();
