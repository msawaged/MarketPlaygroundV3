# Social bot (Instagram + TikTok)

Runs on your Mac twice a day (9:40 am and 5:10 pm). Each run picks a random kind of post and never repeats the last kind:

| Type | Video | Caption |
|---|---|---|
| story (most often) | 20-30 s vertical reel of one of today's news stories (Story mode, via `make_reel.js`) | headline, what it could mean, the tickers it touches |
| scorecard | the Brain's public scorecard with a slow zoom | the live % of #1 picks that beat the S&P 500, from `/v4/brain` |
| pitch | the welcome screen with a slow zoom | what the app does |

Every caption ends with "Practice money. Not investment advice." The same story is never posted twice, and there are at most 2 posts a day (`max_per_day`).

It posts only through the official APIs (Instagram API with Instagram Login, TikTok Content Posting API). It never clicks through the apps, which is what gets accounts banned.

## Setup (about 30 minutes, once)

1. **Install:** `bash scripts/social/install_mac.sh`. This installs ffmpeg, Playwright and Chromium, creates `~/.mp_social/config.json` and schedules the job. It starts in **dry-run mode**: it renders posts into `~/.mp_social/out/` and publishes nothing.
2. **Instagram:**
   - Switch the account to Professional (Creator or Business), in the Instagram app's settings.
   - At developers.facebook.com, create an app (type Business) and add the **Instagram** product ("API setup with Instagram login").
   - Add your account and click **Generate token**.
   - Put the token and your IG user id in `config.json` under `instagram`, and set `"enabled": true`.
   - The bot refreshes the 60-day token on its own.
3. **TikTok:**
   - At developers.tiktok.com, create an app and add **Login Kit** and **Content Posting API** (turn on Direct Post).
   - Add the redirect URI `https://marketplayground-web.onrender.com/welcome`.
   - Put the client key and secret in `config.json`.
   - Run `node scripts/social/tiktok_auth.js url`, open the link, approve, and copy `code=` from the address bar.
   - Run `node scripts/social/tiktok_auth.js <code>`.
   - **Until TikTok audits the app, posts are private (only you can see them).** Submit the app for review in the developer portal. Once it's approved, posts go public with no change needed here.
4. **Try it:** `node scripts/social/post.js --dry-run` (add `--type story|scorecard|pitch` to pick one). Watch the video in `~/.mp_social/out/`.
5. **Go live:** set `"live": true` in `config.json`.

Logs are in `~/.mp_social/bot.log`. To stop the bot: `launchctl unload ~/Library/LaunchAgents/com.mulabs.mp-social.plist`.

Notes:
- If the Mac is asleep at a scheduled time, the post goes out when it wakes.
- Bot videos are silent; adding a trending sound in the app is fine. The daily "Market's open" reel (scripts/make_reel.js) has a voiceover (scripts/reel_voice.py) and no music, so a trending sound can go under it at low volume.
- Tokens stay in `~/.mp_social` (chmod 600), never in the repo.

## Queue (approved one-off posts)

Put `video.mp4` + `caption.txt` in `scripts/social/queue/<yyyy-mm-dd-name>/`. The next run posts the oldest unposted
item instead of an auto-made one (once; tracked in `state.json` `queue_done`). Each run does a `git pull --ff-only`
first, so items pushed to `v4-polish` reach the Mac on their own. Only Murad-approved posts go in the queue.
