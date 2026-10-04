/* Apply the saved theme before first paint (no flash). Keep in sync with src/hooks/useTheme.js */
      (function () {
        var pref = 'system';
        try { var v = localStorage.getItem('ma-theme'); if (v === 'light' || v === 'dark') pref = v; } catch {
    /* storage unavailable: fall back to the system preference */
  }
        var dark = !(window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches);
        var t = pref === 'system' ? (dark ? 'dark' : 'light') : pref;
        var r = document.documentElement;
        r.setAttribute('data-theme', t);
        r.setAttribute('data-theme-pref', pref);
        r.style.colorScheme = t;
        var m = document.querySelector('meta[name="theme-color"]');
        if (m) m.setAttribute('content', t === 'light' ? '#f2f4f8' : '#0d1014');
      })();
