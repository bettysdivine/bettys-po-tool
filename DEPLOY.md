# Betty's Divine PO Tool — Deployment Guide
## What You're Deploying
A private web app that lets you drag a vendor invoice PDF → AI reads it → creates a Purchase Order in Shopify. Bookmarkable on every Mac in the shop.

---

## Step 1 — Create a Railway Account
1. Go to **railway.app**
2. Sign up with GitHub (free — create a GitHub account first if needed)

---

## Step 2 — Deploy the Backend
1. In Railway, click **New Project → Deploy from GitHub repo**
   - OR click **New Project → Empty Project**, then **Add Service → GitHub Repo**
2. Connect your GitHub account and upload the `backend/` folder as a repo
   - Easiest: go to **github.com**, create a new repo called `bettys-po-tool`, upload all files from the `backend/` folder
3. Railway will detect it's a Python app and deploy automatically

---

## Step 3 — Set Environment Variables in Railway
In your Railway service, click **Variables** and add:

| Variable | Value |
|---|---|
| `ANTHROPIC_API_KEY` | your sk-ant-... key |
| `SHOPIFY_ACCESS_TOKEN` | your shpat_... token (regenerate a fresh one!) |
| `SHOPIFY_STORE_URL` | `bettys-divine.myshopify.com` |
| `APP_PASSWORD` | `Bettys1300!` |
| `SECRET_KEY` | any random string, like `bettys-divine-2026-secret` |

---

## Step 4 — Get Your Public URL
Railway gives you a URL like `https://bettys-po-tool-production.up.railway.app`

Copy that URL.

---

## Step 5 — Update the Frontend
Open `frontend/index.html` in a text editor.

Find this line:
```
const API_BASE = window.location.hostname === 'localhost'
```

The app is already set up to use the same origin in production — no changes needed if you host the frontend on Railway too.

**To host the frontend:** Add a second service in Railway, upload the `frontend/` folder, and Railway will serve it as a static site.

OR simply open `index.html` in a browser — it works as a local file too, but you'll need to update `API_BASE` to your Railway backend URL.

---

## Step 6 — Bookmark It!
Once live, bookmark the frontend URL on every Mac in the shop. Done. ✦

---

## Security Reminder
After deployment, have Sam regenerate the Shopify access token in Shopify Admin (same place she created it). The old one was shared in chat. Takes 30 seconds.

---

## Monthly Cost
- Railway hosting: ~$5/month
- Anthropic API: pennies per invoice (fractions of a cent each)
- Shopify API: free

Total: **~$5–7/month** forever.
