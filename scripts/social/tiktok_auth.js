#!/usr/bin/env node
// One-time TikTok login for the bot.
//   1) node scripts/social/tiktok_auth.js url    -> open the printed link, approve, copy the "code" from the address bar
//   2) node scripts/social/tiktok_auth.js <code> -> saves the tokens into ~/.mp_social/config.json
// The redirect URI must be listed in your TikTok app's Login Kit settings exactly as REDIRECT below.
const fs = require('fs');
const os = require('os');
const path = require('path');

const CONFIG = path.join(process.env.MP_SOCIAL_HOME || path.join(os.homedir(), '.mp_social'), 'config.json');
const REDIRECT = process.env.TT_REDIRECT || 'https://marketplayground-web.onrender.com/welcome';
const cfg = JSON.parse(fs.readFileSync(CONFIG, 'utf8'));
const tt = cfg.tiktok;
const arg = process.argv[2];

(async () => {
  if (!arg || arg === 'url') {
    const u = new URL('https://www.tiktok.com/v2/auth/authorize/');
    u.search = new URLSearchParams({ client_key: tt.client_key, scope: 'user.info.basic,video.publish', response_type: 'code',
      redirect_uri: REDIRECT, state: Math.random().toString(36).slice(2) });
    console.log(`Open this, approve, then copy the code= value from the address bar:\n\n${u}\n`);
    return;
  }
  const r = await fetch('https://open.tiktokapis.com/v2/oauth/token/', {
    method: 'POST', headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ client_key: tt.client_key, client_secret: tt.client_secret, code: decodeURIComponent(arg),
      grant_type: 'authorization_code', redirect_uri: REDIRECT }),
  });
  const b = await r.json();
  if (!b.refresh_token) { console.error('TikTok said:', b); process.exit(1); }
  Object.assign(tt, { access_token: b.access_token, refresh_token: b.refresh_token, enabled: true });
  fs.writeFileSync(CONFIG, JSON.stringify(cfg, null, 2), { mode: 0o600 });
  console.log('Saved. TikTok is enabled in', CONFIG);
})().catch((e) => { console.error(e); process.exit(1); });
