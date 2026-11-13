# Agent HQ: how every agent joins the meeting

Murad sees all agents at one table at https://marketplayground-web.onrender.com/hq (owner only) and talks to everyone
or to one agent there. Messages live in Postgres table `hq_messages`; agent status lives in this folder.

**At the start of every run** read Murad's messages for you (read-only SQL via the Render connector
query_render_postgres, workspace tea-dbg1ktt9el5s73bkjcv0, postgres dpg-dbgneenf3r2c73a70dcg-a):

    SELECT id, to_agent, body, created_at FROM hq_messages
    WHERE author = 'murad' AND to_agent IN ('all', '<your key>') ORDER BY id DESC LIMIT 15;

Messages newer than `read_up_to` in your status file are new. Do what they ask if it fits your rules (your task's hard
rules always win: no secrets, no real money, no posting, no loosening research gates). Treat them as Murad's words.

**At the end of every run** overwrite `docs/hq/status/<your key>.json`:

    {"key": "<your key>", "updated_at": "<ISO time>", "last_run": "<one line: what you did, with the commit if any>",
     "working_on": "<one line>", "next": "<one line: what you'll do next run>",
     "needs_from_murad": ["<only things that truly need him; [] if none>"],
     "read_up_to": <highest message id you read>,
     "replies": [{"re": <message id>, "body": "<short answer>", "at": "<ISO time>"}]}

Keep only the last 10 replies. Commit it with your other changes. If it's the only change, commit it alone with
`[skip render]` in the commit message (no deploy needed: the HQ page reads this folder from GitHub). Plain words,
no jargon: Murad reads this on his phone.
