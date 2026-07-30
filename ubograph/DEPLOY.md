# Putting Sanctions+ on a public URL

This is a Python web app, not a static site, so Netlify / GitHub Pages / Vercel's
static hosting won't run it — those serve files, and this needs a process that can
call the sanctions APIs and build PDFs.

Everything below gives you a working `https://something.provider.com` on a free
tier. **Render is the recommended one** — no card, no Docker, deploys from GitHub.

---

## Before you deploy: two things that matter

**1. Set a password.** A deployed instance searches on *your* API keys. Without a
password, anyone who finds the URL spends your OpenSanctions and OpenCorporates
quota, and the first you'll know is a rate-limit error mid-demo. Set `APP_PASSWORD`
and the whole app sits behind a browser login prompt. Leave it unset locally.

**2. Keys go in the host's environment variables, never in the repository.** The
`.env` file is git-ignored and is not uploaded. Each platform below has a place to
paste secrets.

---

## Render (recommended)

1. Push your code to GitHub (already done for this branch).
2. Sign up at [render.com](https://render.com) with your GitHub account.
3. **New → Blueprint**, pick this repository, and set the branch to
   `claude/gnn-shell-company-detection-hukucy`. Render reads `render.yaml` from
   the **repository root** (it does not look inside subdirectories — the file
   points at the `ubograph/` folder itself via `rootDir`) and configures the
   build, start command and health check for you.
4. It will prompt for the secrets marked `sync: false`. Fill in:
   - `OPENSANCTIONS_API_KEY`
   - `OPENCORPORATES_API_TOKEN`
   - `ANTHROPIC_API_KEY` (optional)
   - `APP_PASSWORD` — pick something; the username is `sanctionsplus`
5. Deploy. First build takes a few minutes. You get `https://sanctions-plus.onrender.com`
   (the name is taken from `render.yaml`; adjust it there if it clashes).

**The free-tier catch:** the instance sleeps after about 15 minutes of no traffic,
and the next request has to start it again — roughly a minute of blank screen. For
a demo, open the URL a few minutes beforehand and leave the tab loaded. Do not
discover this in front of judges.

Prefer clicking through to a Blueprint? **New → Web Service** works too — set root
directory `ubograph`, build `pip install -r requirements.txt`, start
`gunicorn server:app --bind 0.0.0.0:$PORT`, then add the same environment variables.

---

## Hugging Face Spaces (no sleep-on-idle in the same way)

Good if the Render cold start bothers you; Spaces stay warm longer and only pause
after a couple of days idle.

1. [huggingface.co](https://huggingface.co) → **New Space** → SDK: **Docker**.
2. Push the contents of `ubograph/` to the Space repo (the `Dockerfile` here is
   ready; it listens on port 7860, which is what Spaces expects).
3. Space **Settings → Variables and secrets** → add the same keys as above.
4. You get `https://<user>-<space>.hf.space`.

Set the Space to **private** if you'd rather not password-protect it, though the
password is still worth having.

---

## Fly.io / Koyeb / Google Cloud Run

All three take the included `Dockerfile` directly. Fly and Cloud Run want a card
on file even on the free allowance; Koyeb gives one free service without one. The
start command is already in the Dockerfile — set the same environment variables in
the platform's dashboard and you're done.

---

## One to avoid: PythonAnywhere

The free tier only permits outbound requests to a whitelist of approved sites.
OpenSanctions and OpenCorporates are not on it, so the app deploys, loads, and
then every search fails. It looks like a bug in the code and isn't.

---

## If the deploy fails

Open the service in Render and read the **Logs** tab — the reason is always
there, and it is usually one of these:

| What the log says | Cause |
|---|---|
| Build succeeds, then "health check failed" / "service unhealthy" | The probe at `/healthz` isn't answering. It is exempt from the password by design; if you changed that, put it back. |
| `ModuleNotFoundError` on start | The build ran in the wrong directory. `rootDir` must be `ubograph`. |
| `bash: gunicorn: command not found` | `requirements.txt` didn't install — check the build log above the failure. |
| Deploy "succeeded" but the URL 401s | That's the password working. Log in with username `sanctionsplus`. |

Paste the last twenty lines of the log if none of those fit.

---

## After deploying — check it actually works

```
curl -u sanctionsplus:YOURPASSWORD https://your-app.onrender.com/api/status
```

Should return `"opensanctions": true, "opencorporates": true`. If a source shows
`false`, the environment variable didn't land — check for a stray space or quote
marks around the value in the dashboard.

Then open the URL in a browser, log in, and run one real search. The header chips
tell you what's live, and any API error appears in red in the left panel rather
than failing silently.

## Ongoing monitoring (the Workspace tab's watchlist)

The watchlist re-screens a name only when something calls
`POST /api/watchlist/check_all` — there's no scheduler built into the app,
because Render's free tier doesn't run background workers. To make it actually
"ongoing":

1. **Free option:** point [cron-job.org](https://cron-job.org) (or any similar
   free scheduler) at
   `https://your-app.onrender.com/api/watchlist/check_all`, method `POST`,
   with HTTP Basic Auth set to your `sanctionsplus` / `APP_PASSWORD`
   credentials, once a day or once a week.
2. **Paid option:** Render's own **Cron Jobs** (a separate paid service type)
   can run `curl -u sanctionsplus:$APP_PASSWORD -X POST
   https://your-app.onrender.com/api/watchlist/check_all` on a schedule.

Either way, each check spends live API quota per watched name — daily or
weekly is plenty; don't point a scheduler at it every few minutes.

## Cost

Everything above is free at the tier described. What is *not* free is your API
quota: each search makes a match call plus entity expansions, so a public URL
without a password can drain a trial key quickly. That is the whole reason
`APP_PASSWORD` exists. Cases, the watchlist and the activity log live in a
SQLite file on local disk (see README's Workspace section) — free, but reset
on every redeploy and free-tier spin-down.
