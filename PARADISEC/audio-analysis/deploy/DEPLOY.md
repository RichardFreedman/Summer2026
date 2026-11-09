# Deploying "Exploring sound with librosa"

The app runs on the CRIM DigitalOcean droplet (`intervals424`), alongside TLJH and the
other Streamlit apps, at **https://sound.crimproject.org**.

It follows the same pattern as `intervals-streamlit` and `theory-llm`:

| | |
|---|---|
| Runs as | systemd service `exploring-sound` (no Docker) |
| Code and audio | `/root/exploring_sound/app/` (copied from a Mac with rsync, not git) |
| Python | 3.13 in `/root/exploring_sound/venv/`, installed with `uv` (the system Python 3.10 is untouched) |
| Port | `localhost:8503` (8501 = theory-llm, 8502 = intervals-streamlit) |
| Web routing and HTTPS | TLJH's Traefik, rule file `/opt/tljh/state/rules/exploring_sound.toml` |
| Password | `app_password` in `/root/exploring_sound/app/.streamlit/secrets.toml` |

The audio in `extra_audio/` is partly under copyright. It is never committed to git
(see `.gitignore`) and reaches the server only by rsync. The same goes for the real list
of examples, `extra_audio/extra_metadata.csv`. Git carries only
`extra_metadata.sample.csv`, which lists the openly licensed CRIM clip, and the app
falls back to it when the real list is absent (as in a fresh clone). The app shows a password
page first, and no audio is sent to the browser until the password is entered.

Commands marked **Mac** run in Terminal on your own machine. Commands marked
**droplet** run in the DigitalOcean console (or `ssh root@intervals.crimproject.org`).

---

## First-time setup

### 1. DNS

Wherever the DNS for `crimproject.org` is managed, add an **A record**:

| Type | Name | Value |
|---|---|---|
| A | `sound` | the droplet's IP (the same one `intervals-streamlit.crimproject.org` uses) |

Do this first, so the record has spread by the time the app is running. To check
it from the Mac:

```bash
dig +short sound.crimproject.org
dig +short intervals-streamlit.crimproject.org   # the two should match
```

### 2. Create the folder and install Python 3.13 (droplet)

```bash
ss -tlnp | grep 8503 || echo "8503 is free"
mkdir -p /root/exploring_sound/app
curl -LsSf https://astral.sh/uv/install.sh | sh && source ~/.local/bin/env
uv venv --python 3.13 /root/exploring_sound/venv
```

`uv` downloads its own Python 3.13 into `~/.local/share/uv`. It does not change the system
Python or the other apps' environments.

### 3. Copy the app and audio to the droplet (Mac)

This needs SSH access from the Mac to the droplet. `ssh root@intervals.crimproject.org`
should log in without a password prompt. If it doesn't, add the Mac's public key
(`~/.ssh/id_ed25519.pub`) to `/root/.ssh/authorized_keys` on the droplet.

```bash
rsync -av --exclude .venv --exclude __pycache__ --exclude .DS_Store \
  --exclude .streamlit/secrets.toml \
  ~/Documents/CRIM_Python/Summer2026/PARADISEC/audio-analysis/ \
  root@intervals.crimproject.org:/root/exploring_sound/app/
```

This also copies `soundscape/` (the roughly 60 MB of public PARADISEC excerpts). If that
folder is not on the Mac, run `./fetch_data.sh` in `/root/exploring_sound/app` on the
droplet after this step.

### 4. Install packages and set the password (droplet)

```bash
cd /root/exploring_sound/app
uv pip install --python /root/exploring_sound/venv/bin/python -r requirements.txt
printf 'app_password = "choose-a-password"\n' > .streamlit/secrets.toml
chmod 600 .streamlit/secrets.toml
```

The password lives in this file rather than in the service file, because files in
`/etc/systemd/system/` can be read by any user on the server.

### 5. Start the service (droplet)

```bash
cp deploy/exploring-sound.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now exploring-sound
sleep 15
curl -sI http://localhost:8503/ | head -1     # expect: HTTP/1.1 200 OK
```

`enable` makes it start again after a reboot, and `Restart=always` brings it back if it crashes.

### 6. Route the subdomain through Traefik (droplet)

```bash
cp deploy/exploring_sound.toml /opt/tljh/state/rules/exploring_sound.toml
```

Traefik watches that folder and picks the file up within seconds, with no restart needed.

### 7. Check it

Open **https://sound.crimproject.org**. You should see the password page. The very
first visit can take a few seconds while Let's Encrypt issues the certificate.

---

## Adding new audio examples

New audio files (`*.mp3`, `*.wav`, `*.flac`, `*.ogg`, `*.m4a`, `*.aiff`) and the real
`extra_metadata.csv` are ignored by git. They are never committed or pushed, and
`git pull` never touches them. Edit the CSV freely.

**On the Mac**

1. Put the file in `extra_audio/`.
2. Add a row to `extra_audio/extra_metadata.csv`:

   | column | meaning |
   |---|---|
   | `file` | the audio file name in `extra_audio/` |
   | `item` | short identifier, e.g. `CRIM-0012` |
   | `kind` | `music` or `speech` |
   | `title`, `description`, `year` | shown in the sidebar (year may be blank) |
   | `collection`, `url` | grouping label and the "Open the source page" link |
   | `credit`, `licence` | shown under the title |

3. Optional: to show it in the default list, add its `item` to `CURATED` in `analysis.py`.
4. Test locally: `streamlit run streamlit_app.py`.

**Send it to the droplet (Mac)**

```bash
cd ~/Documents/CRIM_Python/Summer2026/PARADISEC/audio-analysis
rsync -av extra_audio/ root@intervals.crimproject.org:/root/exploring_sound/app/extra_audio/
rsync -av analysis.py root@intervals.crimproject.org:/root/exploring_sound/app/   # only if CURATED changed
```

**Restart (droplet)**

```bash
systemctl restart exploring-sound
```

The restart is needed because the app caches the list of clips. Features for the new
example are computed the first time it is opened, so nothing else needs rebuilding.

> Only add a row to `extra_metadata.sample.csv` (the committed one) for audio that is
> itself committed and freely licensed, like the CRIM clip. The app fails if a row lists an
> audio file that isn't there, so a sample row for private audio would break public clones.

## Removing an audio example

1. On the Mac, delete the file from `extra_audio/` and its row from `extra_metadata.csv`
   (and its `item` from `CURATED` in `analysis.py`, if it is there).
2. Send the CSV (and `analysis.py` if changed) to the droplet with the rsync commands above.
3. On the droplet, delete the audio file too. rsync never deletes anything on the
   server, because these commands don't use `--delete`:

   ```bash
   rm "/root/exploring_sound/app/extra_audio/<file>"
   systemctl restart exploring-sound
   ```

---

## Updating the code

Run the full rsync from step 3 again. It sends only what has changed. Then:

```bash
systemctl restart exploring-sound           # droplet
```

If `requirements.txt` changed, first run the `uv pip install` line from step 4.

## Changing the password

```bash
nano /root/exploring_sound/app/.streamlit/secrets.toml     # droplet
systemctl restart exploring-sound
```

The rsync excludes `secrets.toml`, so updates from the Mac never overwrite it.

---

## Troubleshooting (droplet)

| Symptom | Check |
|---|---|
| Is the app running? | `systemctl status exploring-sound --no-pager` |
| App errors | `journalctl -u exploring-sound -n 50 --no-pager` (add `-f` to follow live) |
| Works on `localhost:8503` but not on the web | `journalctl -u traefik -n 30 --no-pager`, and that the rule file is in `/opt/tljh/state/rules/` |
| Certificate error in the browser | DNS not pointing at the droplet yet (`dig +short sound.crimproject.org`); Let's Encrypt needs it to reach the server |
| "No password is configured" | `secrets.toml` is missing or has no `app_password` line |
| Port clash | `ss -tlnp \| grep 8503` |

To take the app offline:

```bash
systemctl disable --now exploring-sound
rm /opt/tljh/state/rules/exploring_sound.toml
```

---

## Keeping copyrighted audio out of git

- `.gitignore` only affects files git is not already tracking. Check what is tracked with
  `git ls-files extra_audio`. Only `CRIM_Model_0012.mp3` (CC BY-NC) and
  `extra_metadata.sample.csv` should be listed.
- If anything else is listed, stop tracking it with `git rm --cached "extra_audio/<file>"`
  and commit. **Back the file up first**: any other clone that pulls that commit will have
  the file deleted from its disk.
- Removing a file in a new commit does not remove it from GitHub. Earlier commits still
  contain it. Taking it down means rewriting the branch history and force-pushing, and
  possibly asking GitHub support to purge cached copies.
- Never use `git add -f` on audio files.

## One-time switch to the sample CSV (Mac)

`extra_metadata.csv` used to be tracked in git. Run this once to stop tracking it. The
file stays on disk, and the server doesn't use git, so it is unaffected:

```bash
cd ~/Documents/CRIM_Python/Summer2026/PARADISEC/audio-analysis
git rm --cached extra_audio/extra_metadata.csv
git add extra_audio/extra_metadata.sample.csv .gitignore analysis.py
git commit -m "Keep the real example list local; commit a sample CSV"
git push
```

Anyone else with a clone should copy their `extra_metadata.csv` aside before pulling
that commit, since the pull deletes it from their disk, and then put it back.

## Files in `deploy/`

- `exploring-sound.service`: the systemd service (copied to `/etc/systemd/system/`)
- `exploring_sound.toml`: the Traefik route (copied to `/opt/tljh/state/rules/`)
- `DEPLOY.md`: this guide
