# Weekly Workflow — Every Monday

This is your repeatable Monday morning process. Start to published: 30–45 minutes.

---

## The 7-step Monday workflow

### Step 1 — Run the scraper (5 min)

```bash
ssh mww@10.127.31.35
cd /opt/modern-work-weekly/scraper
source .venv/bin/activate
python scraper.py
```

Output: `../state/weekly_draft_YYYY-MM-DD.json`

If a source is down or slow, run individual sources:
```bash
python scraper.py --source Intune
python scraper.py --source Entra
```

---

### Step 2 — Review the raw draft (5 min)

Open the JSON file. Quickly scan:
- Are there obvious duplicates the dedup missed? (same feature, slightly different heading)
- Are there items from the past 2+ weeks that Microsoft backdated?
- Any sources that returned 0 items? (Could mean site structure changed — check the log)

```bash
cat /opt/modern-work-weekly/state/weekly_draft_$(date +%Y-%m-%d).json | python3 -m json.tool | less
```

---

### Step 3 — Generate digest in Claude.ai (10–15 min)

1. Open [claude.ai](https://claude.ai) → your **Modern Work Weekly** Project
2. The master prompt is already saved as the Project instruction
3. Paste the JSON draft into a new chat message
4. Add: `"Generate this week's digest in the standard format."`
5. Claude produces the full digest — review, edit, fact-check anything that looks off

**Tips:**
- If an item is thin on detail, ask Claude: `"Expand the Defender XDR attack disruption item with more operational context"`
- If something looks wrong, check the source URL in the JSON item directly
- The Top 5 ranking is Claude's suggestion — reorder if your engineering judgment disagrees

---

### Step 4 — Save the digest as a Hugo post (5 min)

On your local machine (where you have the repo cloned):

```bash
# Create a new post from the archetype
cd ~/modern-work-weekly/site
hugo new content/posts/$(date +%Y-%m-%d).md
```

Or just copy the archetype manually:
```bash
cp site/archetypes/posts.md site/content/posts/$(date +%Y-%m-%d).md
```

Paste the Claude-generated digest content into the file. Update the front matter:
- `title`: set the date
- `description`: 1–2 sentence summary of this week's theme
- `tags`: add/remove based on actual content

---

### Step 5 — Push to GitHub (2 min)

```bash
cd ~/modern-work-weekly
git add site/content/posts/
git commit -m "digest: $(date +%Y-%m-%d)"
git push origin main
```

GitHub Actions picks this up → builds Hugo → rsync to LXC → live within ~2 minutes.

Check: `https://firstlast.dev` — new post should appear at the top.

Check the Actions tab on GitHub if anything looks wrong.

---

### Step 6 — Generate the LinkedIn paste (2 min)

```bash
cd ~/modern-work-weekly
python linkedin/formatter.py site/content/posts/$(date +%Y-%m-%d).md
```

This prints the LinkedIn-formatted version to stdout. Pipe to clipboard:

```bash
# macOS
python linkedin/formatter.py site/content/posts/$(date +%Y-%m-%d).md | pbcopy

# Linux (xclip)
python linkedin/formatter.py site/content/posts/$(date +%Y-%m-%d).md | xclip -selection clipboard
```

Or save to file:
```bash
python linkedin/formatter.py site/content/posts/$(date +%Y-%m-%d).md \
  --output /tmp/linkedin_$(date +%Y-%m-%d).txt
```

---

### Step 7 — Post to LinkedIn (5 min)

Two options depending on length:

**Short week (under 3,000 chars) → Regular LinkedIn post**
- Paste directly into LinkedIn post composer
- Add a link to your blog post at the end
- Add the hashtag block

**Normal/long week → LinkedIn Article**
- Go to LinkedIn → Write article
- Use the article template from `linkedin/template.md` as structure reference
- Copy sections from the formatter output
- Publish → share to your feed with a short intro post

**Timing:** Post between 8–10am Tuesday or Wednesday for best B2B engagement. Monday morning competes with everyone else's weekly roundups.

---

## Quick checklist

```
[ ] scraper.py run — draft JSON in state/
[ ] JSON reviewed for dupes/gaps
[ ] Claude.ai digest generated and edited
[ ] site/content/posts/YYYY-MM-DD.md saved with correct front matter
[ ] git push → GitHub Actions → site live
[ ] LinkedIn paste generated
[ ] LinkedIn post/article published
[ ] Shared from personal profile with brief intro
```

---

## Troubleshooting

**Scraper returns 0 new items**
- Check `logs/scraper_YYYYMMDD.log` for errors
- Run `--force-all` to bypass dedup and see if items come through: `python scraper.py --force-all`
- Microsoft sometimes restructures their Learn pages — check `sources.py` selectors

**GitHub Action fails on rsync step**
- Verify `HOMELAB_HOST`, `HOMELAB_USER`, `HOMELAB_SSH_KEY` secrets are set correctly
- Test SSH manually: `ssh mww@10.127.31.35`
- Check that port 22 is reachable from GitHub Actions egress IPs

**Site not updating after push**
- Check GitHub Actions run → look for rsync output
- SSH to LXC: `ls -la /opt/modern-work-weekly/site/public/posts/` — did the file land?
- Check Caddy: `systemctl status caddy` and `journalctl -u caddy -n 50`
- Check Cloudflare Tunnel: `systemctl status cloudflared`

**Cloudflare tunnel disconnected**
- `systemctl restart cloudflared`
- Check: `cloudflared tunnel info modern-work-weekly`
