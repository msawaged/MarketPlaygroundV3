// Official posting APIs only (no app automation, which gets accounts banned).
//   Instagram: Instagram API with Instagram Login, Reels via resumable upload of a local file.
//   TikTok:    Content Posting API, Direct Post with FILE_UPLOAD.
const fs = require('fs');

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function j(res, what) {
  const text = await res.text();
  let body; try { body = JSON.parse(text); } catch { body = { raw: text }; }
  if (!res.ok) throw new Error(`${what}: HTTP ${res.status} ${text.slice(0, 300)}`);
  return body;
}

// ---------------- Instagram ----------------

async function igRefresh(cfg) {
  // Long-lived tokens last 60 days; refresh when older than ~30 so it never lapses.
  const age = Date.now() - Date.parse(cfg.refreshed_at || 0);
  if (age < 30 * 864e5) return false;
  const u = new URL(`https://${cfg.host || 'graph.instagram.com'}/refresh_access_token`);
  u.search = new URLSearchParams({ grant_type: 'ig_refresh_token', access_token: cfg.access_token });
  const b = await j(await fetch(u), 'instagram token refresh');
  cfg.access_token = b.access_token;
  cfg.refreshed_at = new Date().toISOString();
  return true;
}

async function igPostReel(cfg, videoPath, caption) {
  const host = cfg.host || 'graph.instagram.com';
  const v = cfg.api_version || 'v21.0';
  const base = `https://${host}/${v}`;
  const size = fs.statSync(videoPath).size;

  // 1. create an upload container
  const c = new URL(`${base}/${cfg.user_id}/media`);
  c.search = new URLSearchParams({ media_type: 'REELS', upload_type: 'resumable', caption, share_to_feed: 'true', access_token: cfg.access_token });
  const container = await j(await fetch(c, { method: 'POST' }), 'instagram create container');
  const id = container.id;
  const uploadUri = container.uri || `https://rupload.facebook.com/ig-api-upload/${v}/${id}`;

  // 2. upload the file
  await j(await fetch(uploadUri, {
    method: 'POST',
    headers: { Authorization: `OAuth ${cfg.access_token}`, offset: '0', file_size: String(size) },
    body: fs.readFileSync(videoPath),
  }), 'instagram upload');

  // 3. wait for Instagram to process it
  for (let i = 0; i < 60; i++) {
    const s = new URL(`${base}/${id}`);
    s.search = new URLSearchParams({ fields: 'status_code,status', access_token: cfg.access_token });
    const st = await j(await fetch(s), 'instagram status');
    if (st.status_code === 'FINISHED') break;
    if (st.status_code === 'ERROR' || st.status_code === 'EXPIRED') throw new Error(`instagram processing failed: ${JSON.stringify(st)}`);
    if (i === 59) throw new Error('instagram processing timed out');
    await sleep(5000);
  }

  // 4. publish
  const p = new URL(`${base}/${cfg.user_id}/media_publish`);
  p.search = new URLSearchParams({ creation_id: id, access_token: cfg.access_token });
  const pub = await j(await fetch(p, { method: 'POST' }), 'instagram publish');
  return pub.id;
}

// ---------------- TikTok ----------------

const TT = 'https://open.tiktokapis.com/v2';

async function ttRefresh(cfg) {
  // Access tokens last 24h; the refresh token lasts a year and may rotate, so save both.
  const b = await j(await fetch(`${TT}/oauth/token/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ client_key: cfg.client_key, client_secret: cfg.client_secret,
      grant_type: 'refresh_token', refresh_token: cfg.refresh_token }),
  }), 'tiktok token refresh');
  if (!b.access_token) throw new Error(`tiktok token refresh: ${JSON.stringify(b).slice(0, 300)}`);
  cfg.access_token = b.access_token;
  if (b.refresh_token) cfg.refresh_token = b.refresh_token;
  return true;
}

async function ttPostVideo(cfg, videoPath, caption) {
  const auth = { Authorization: `Bearer ${cfg.access_token}`, 'Content-Type': 'application/json; charset=UTF-8' };

  // TikTok requires checking the creator's allowed privacy levels before every post.
  const info = await j(await fetch(`${TT}/post/publish/creator_info/query/`, { method: 'POST', headers: auth }), 'tiktok creator info');
  const allowed = info?.data?.privacy_level_options || [];
  const want = cfg.privacy_level || 'SELF_ONLY';
  const privacy = allowed.includes(want) ? want : (allowed.includes('SELF_ONLY') ? 'SELF_ONLY' : allowed[0]);
  if (!privacy) throw new Error(`tiktok: no privacy level allowed (${JSON.stringify(info).slice(0, 200)})`);
  if (privacy !== want) console.warn(`[tiktok] ${want} not allowed for this app yet; posting as ${privacy}. (Unaudited apps can only post privately.)`);

  const size = fs.statSync(videoPath).size;
  const init = await j(await fetch(`${TT}/post/publish/video/init/`, {
    method: 'POST', headers: auth,
    body: JSON.stringify({
      post_info: {
        title: caption.slice(0, 2200), privacy_level: privacy,
        disable_duet: false, disable_comment: false, disable_stitch: false, video_cover_timestamp_ms: 1000,
        brand_content_toggle: false, brand_organic_toggle: true, // promoting your own business: TikTok requires this disclosure
      },
      source_info: { source: 'FILE_UPLOAD', video_size: size, chunk_size: size, total_chunk_count: 1 },
    }),
  }), 'tiktok init');
  const { publish_id: publishId, upload_url: uploadUrl } = init.data || {};
  if (!uploadUrl) throw new Error(`tiktok init: ${JSON.stringify(init).slice(0, 300)}`);

  const up = await fetch(uploadUrl, {
    method: 'PUT',
    headers: { 'Content-Type': 'video/mp4', 'Content-Length': String(size), 'Content-Range': `bytes 0-${size - 1}/${size}` },
    body: fs.readFileSync(videoPath),
  });
  if (!up.ok) throw new Error(`tiktok upload: HTTP ${up.status} ${(await up.text()).slice(0, 200)}`);

  for (let i = 0; i < 60; i++) {
    const st = await j(await fetch(`${TT}/post/publish/status/fetch/`, { method: 'POST', headers: auth, body: JSON.stringify({ publish_id: publishId }) }), 'tiktok status');
    const s = st?.data?.status;
    if (s === 'PUBLISH_COMPLETE' || s === 'SEND_TO_USER_INBOX') return publishId;
    if (s === 'FAILED') throw new Error(`tiktok publish failed: ${st.data.fail_reason || JSON.stringify(st)}`);
    await sleep(5000);
  }
  return publishId; // still processing; TikTok finishes it on its side
}

module.exports = { igRefresh, igPostReel, ttRefresh, ttPostVideo };
