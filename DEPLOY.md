# Putting Stock Agent online (private, for your own devices)

This hosts the app on **Render** (free) so you can open it from your phone,
laptop, anywhere — behind a password only you know. It connects straight to
this GitHub repo, so every time you `git push`, the site updates itself.

Takes about 10 minutes. You need a GitHub account (you have one) and you'll make
a free Render account.

---

## 1. Create a Render account

1. Go to **https://render.com** and click **Get Started**.
2. Choose **Sign in with GitHub** and authorize it. (This lets Render see your
   repos so it can deploy them.)

## 2. Create the web service from this repo

1. In the Render dashboard, click **New +** → **Web Service**.
2. Find **martin_stocks** in the list and click **Connect**.
   (If you don't see it, click "Configure account" and give Render access to the
   repo.)
3. Render reads the included `render.yaml` and fills in most settings. Confirm:
   - **Branch:** `main`
   - **Runtime:** Python
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `gunicorn app:app --bind 0.0.0.0:$PORT`
   - **Instance type:** **Free**

## 3. Set your password (this is what makes it private)

Before it deploys, open the **Environment** section and add:

| Key | Value |
|---|---|
| `APP_PASSWORD` | **a password you choose** — this is what you'll type to get in |
| `APP_USERNAME` | `admin` (or any username you like) |

Optional — turn on the Claude AI write-ups:

| Key | Value |
|---|---|
| `ANTHROPIC_API_KEY` | your key from console.anthropic.com (leave out to skip) |

Then click **Create Web Service** (or **Deploy**).

## 4. Wait for it to build

Render installs everything and starts the app — first build takes a few minutes.
When it's done you'll see a URL like:

```
https://stock-agent-xxxx.onrender.com
```

Open that on **any device**. Your browser will pop up a login box — enter the
username (`admin`) and the `APP_PASSWORD` you set. You're in. 🎉

---

## Good to know

- **Bookmark the URL** on your phone. The login is remembered per browser
  session.
- **Free tier sleeps.** After ~15 minutes of no visits the app naps; the next
  visit takes ~30–60 seconds to wake up, then it's fast again. Normal for free
  hosting.
- **Updates are automatic.** When I push a new feature (or you do), Render
  redeploys within a minute or two — no re-download, nothing to do.
- **Your watchlist edits reset on redeploy.** The free tier has no permanent
  disk, so tickers you add via the search bar live only until the next restart.
  Your Base/Middle/Top defaults (in `stock_agent/watchlist.py`) always stick. If
  you want added tickers to persist online, tell me — I'll switch the watchlist
  to a small database (a bit more setup, but then it's permanent).
- **Keep your password to yourself.** Anyone with the URL *and* the password can
  see the site. The password is stored as a secret on Render, never in the code.

## Running it locally still works

Nothing changes for local use — `python app.py` with no `APP_PASSWORD` set runs
open on your own machine as before.
