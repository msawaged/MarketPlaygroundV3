# Growth plan: get MarketPlayground in front of real people this week

Written by the growth agent, Sat Nov 21 2026, after Murad said "do or die".

## Where we stand (honest numbers)

- 10 accounts ever. 0 new accounts in the last 2 weeks.
- 0 ideas from strangers ever (all 34 user ideas came from 7 people we know).
- 0 Close Call answers from strangers ever, though it needs no sign-up.
- TikTok, Nov 9–15: 677 views and 0 new followers. Top video: the Nvidia/Baird downgrade.
- The app itself is open now: free beta, no sign-in needed. **"Coming soon" only lives in the reels.** Their last card says "MarketPlayground is coming soon. Follow for launch day." So every viewer is told not to come yet.

The biggest blocker is not the product. We are telling people to wait, and we can't see whether anyone comes.

## 0. Guerrilla marketing first (Murad, Nov 21: "I want guerrilla marketing")

These are cheap, loud and done in person or on camera. One question does all the work: **"Will NVDA close above $185 on Friday? YES or NO."** Real options prices give the market's odds, and anyone can answer free in 10 seconds. Each stunt ends with a QR code or link to that day's Close Call (`?ref=` tag per stunt, so we know which one worked).

1. **Street-interview reels ("Beat the market?")**
   - Murad stops people on campus or downtown and asks the Close Call question on camera. Then he reveals: "The options market says 65%."
   - Friday's follow-up reel shows who called it.
   - Street interviews are one of TikTok's strongest formats, and it costs nothing but a phone.
   - **First step:** film 10 people Monday. The reel agent cuts 3 reels (one per day) with the face-off, the reveal and "Answer free, link in bio."
2. **QR posters and stickers: "The market says 62%. Do you?"**
   - One huge question, the odds and a QR code to `/close-call?ref=qr-<place>`.
   - Put them where it's allowed: business-school boards, library and café boards, investment-club rooms. A new question each week keeps them fresh.
   - **First step:** growth writes the poster text and the reel agent makes the print file. Murad prints 30 at a library (pennies).
3. **Chalk the question** (only where chalk is allowed; check campus rules):
   - "WILL TESLA CLOSE ABOVE $X FRIDAY? → marketplayground (QR)" outside the business school on Monday.
   - Film people stopping to read it for a reel.
4. **"Humans vs. the Brain" weekly scoreboard reel**
   - Every Friday, show this week's Close Call questions, what people answered, the market's odds and what really happened.
   - Use real numbers, including when the Brain loses. Honest losses are more shareable than bragging.
   - The data exists already (yesno_calls); the reel agent builds the template.
5. **Ride big moments: earnings and Fed days**
   - The night before a big earnings report, post: "Options market: 48% chance X closes higher after earnings. Your call?" Then post the result reel the next day.
   - Comment the market's odds, by hand, under the big finance creators' videos on the same stock: real value, one comment, no links unless asked.
6. **Wear it**
   - Mumu the cow merch (already being designed) with the QR on the back: "Ask me if NVDA closes above $185."
   - Wear it to class, the gym and finance meetups.
7. **Weekly "Called it" bragging rights**
   - The best caller of the week (practice money, opt-in name) gets shouted out in Friday's reel.
   - Being shouted out is the reason to share, and sharing brings their friends.

**Off-limits, even for guerrilla:**

- no fake accounts or fake reviews
- no mass DMs or spam comments
- no flyers or chalk where they aren't allowed
- no "guaranteed" or "buy this" claims

Every piece says "Practice money. Not investment advice." Getting banned or fined would end this faster than no marketing.

Guerrilla needs items 1, 2 and 5 below to be "yes" first (no "coming soon", tagged links, Close Call as the landing page). Otherwise the people we stop on the street land on a page telling them to wait.

## 1. Launch checklist: Murad says yes or no to each

| # | Decision | What happens on "yes" | Who does it |
|---|---|---|---|
| 1 | **Launch: drop "coming soon" from reels** | The reel agent renders with `LIVE=1` (and `/reel?live=1`). The last card says "Make your call free, link in bio." | Reel agent, same day |
| 2 | **Bio link with a platform tag** | TikTok bio gets `marketplayground-web.onrender.com/close-call?ref=tt`, Instagram gets `?ref=ig`, Facebook gets `?ref=fb` | Murad (2 min in each app) |
| 3 | **Count visits by tag** | A tiny counter records each `ref` tag and how many of those visitors answer a Close Call or make a first idea. No cookies or personal data, just counts on the Brain page and in this report | Build chat (~1 hour, 1 deploy) |
| 4 | **Privacy policy and terms pages** (`/privacy`, `/terms`) | Needed before TikTok and Meta will approve auto-posting, and right to have since we collect emails. Plain-language draft; have someone qualified look it over (this is not legal advice) | Build chat drafts, Murad approves the wording |
| 5 | **First tap = Close Call** | The `?ref=` links land on today's Close Call question, with a one-tap YES/NO and no sign-up. After the answer: "Get an email when it's graded" (the existing "You called it" email) | Build chat (small) |
| 6 | **Auto-posting** (section 3) | Daily reels go out on their own through official APIs | Build chat builds it; Murad connects accounts |
| 7 | **Auto-approve daily reels?** | Yes: posts go out after automatic checks, with a 30-minute window where Murad gets a phone ping and can stop it. No: each reel waits for his OK (today's rule) | Murad decides |

Items 1, 2 and 5 can all happen this week with no money spent. Items 3–4 cost one bundled deploy, which keeps Render build spend low.

## 2. Top 3 free channels for a practice-trading app

Murad posts in each one himself. Agents never post.

### A. Reddit: launch subs first, finance subs with real value
- **Why:** finance Reddit is huge, and Close Call ("the options market says 65% NVDA closes above $185 Friday — what do you think?") is a fun, novel hook that isn't an ad.
- **Exact first step (Monday):** post in **r/SideProject**: "I built a free app that turns real options prices into yes/no odds on stock closes. Practice money, no sign-up." Include one screenshot and the link with `?ref=reddit`. Answer every comment that day.
- **Then:** r/alphaandbetausers (asks for feedback, allows links). In r/options and r/stocks, only post useful content (e.g. "what the options market implies for this week's earnings"), and only where each sub's self-promotion rules allow. Read each sub's rules first. Breaking them gets the account banned.

### B. Professors and student investment clubs
- **Why:** students are the perfect users (curious, no money yet, want practice). One professor who likes it can bring a whole class. Prof Brown is already reviewing the app.
- **Exact first step:** Murad asks Prof Brown one thing: "Would you show Close Call for 5 minutes in a class, or introduce me to the student investment club's president?" Link with `?ref=school`.
- **Then:** offer the club a weekly "class Close Call" challenge with a leaderboard, run on practice money. (The leaderboard is a small build; only build it once a club says yes.)

### C. Product Hunt
- **Why:** one free launch day puts us in front of early adopters and gives a permanent backlink. It works best when everything is ready, so it comes after items 1–5.
- **Exact first step:** Murad makes a Product Hunt maker account this week (it's free; new accounts should be active a few days before launching). Pick a Tuesday or Wednesday launch: **Dec 2 or Dec 3**.
- **Prep (agents):** reel agent makes a 45-second demo video and 4 screenshots. Growth writes the tagline ("Real options odds, practice money, no sign-up"), the first maker comment and the gallery text. Ask friends to *try it* that day, not to upvote on command (Product Hunt penalizes vote rings).

Backups if one stalls: finance Discord servers with a #share-your-project channel, and small finance creators (10k–100k followers) who might duet or stitch a Close Call reel.

## 3. Spec: daily auto-posting (for the build chat)

### Don't start from zero
`scripts/social/` already has a working bot (Node): official Instagram and TikTok posting APIs, a queue folder, dry-run mode, a limit of 2 posts a day, and a disclaimer on every caption. Murad asked for "even a Python script". The fastest path is to **extend this bot** instead of rewriting it in Python. If Python is a must, port it with the same behaviour below.

### What to build
1. **Daily reel into the queue, automatically.** At 9:40 am ET on weekdays, run `node scripts/make_reel.js` with `LIVE=1` after launch. Write `scripts/social/queue/<YYYY-MM-DD>-open/` containing `video.mp4`, `caption_tiktok.txt`, `caption_instagram.txt`, `caption_facebook.txt` and `meta.json` (headline, tickers, the numbers used and where each came from).
2. **Automatic checks before posting** (fail = don't post, ping Murad):
   - every caption ends with "Practice money. Not investment advice."
   - every number in the caption appears in `meta.json` from the live API
   - no "buy"/"sell"/"guaranteed" wording
   - the video is 9:16, 15–90 s, under 100 MB
   - not a repeat of an earlier headline
3. **Approval** (Murad's decision 7):
   - `auto` mode posts 30 minutes after a phone ping unless he replies "stop".
   - `manual` mode waits for a `approved` file in the queue folder (today's rule).
4. **Add Facebook** (new in `platforms.js`). Facebook Page Reels API:
   - `POST /{page-id}/video_reels` with `upload_phase=start`
   - upload the file to the returned `upload_url` (rupload.facebook.com)
   - `POST /{page-id}/video_reels` with `upload_phase=finish`, `video_state=PUBLISHED` and `description=<caption>`
5. **Log results.** Record the post ID, URL and time for each platform in `~/.mp_social/state.json`. Once a day, fetch views where the API allows (Instagram insights `views` and `reach`, TikTok `video/query` view_count) so the growth report sees views next to `ref` visits.
6. **Where it runs:** on Murad's Mac (`install_mac.sh` exists; it misses posts while the Mac is asleep), *or* on a GitHub Actions schedule (no Mac needed; tokens stored as GitHub secrets). Murad decides; the Mac needs no new setup.

### Accounts and keys Murad must connect (only he can do this)

| Platform | What he needs | Note |
|---|---|---|
| Instagram | Switch to a Professional (Creator) account. Create a Meta developer app (type Business) with the "Instagram API with Instagram Login" product and permissions `instagram_business_basic` + `instagram_business_content_publish`. Generate a long-lived token and get the IG user ID | The bot refreshes the token itself. Instagram caps API posts per day well above our 1–2 |
| Facebook | A Facebook **Page** for MarketPlayground (not a personal profile). In the same Meta app, add permissions `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`. Get a long-lived **Page** access token and the Page ID | Fine without app review while Murad is the app's admin and posts only to his own Page |
| TikTok | A developer account at developers.tiktok.com. App with Login Kit + Content Posting API (Direct Post on). Redirect URI `https://marketplayground-web.onrender.com/welcome`. Client key + secret, then run `tiktok_auth.js` once | **Until TikTok audits the app, API posts are private (only he sees them).** Submit for audit right away; it needs the privacy and terms URLs from checklist item 4 |

Tokens stay in `~/.mp_social/config.json` (chmod 600) or GitHub secrets. They never go in the repo.

## 4. This week, day by day

- **Sun:** Murad answers the 7 yes/no items. He sets the bio links (item 2) and makes the Facebook Page and Product Hunt account. Growth writes the poster text and the street-interview script.
- **Mon:** build chat ships items 3, 4 and 5 in **one** deploy. Reel agent switches to "live" reels. Murad films 10 street interviews, puts up the QR posters, posts on r/SideProject and asks Prof Brown.
- **Tue–Wed:** Murad connects the Instagram, Facebook and TikTok developer apps and submits the TikTok audit. Build chat adds Facebook and the daily queue to the bot, then tests in dry-run mode.
- **Fri:** first "Humans vs. the Brain" scoreboard reel and the street-interview reveal reel.
- **Thu–Fri:** auto-posting goes live on Instagram and Facebook (TikTok goes public once audited). Post in r/alphaandbetausers.
- **Next Sunday's report:** visits by `ref` tag, Close Call answers from strangers, first ideas and sign-ups. Then we drop whichever channel brought nobody.

**Goal for the week:** 25 strangers answer a Close Call and 5 come back on a second day. Small, but it would be our first real users.
