# Ask the transcripts: deployment

Serves `PARADISEC/transcript-search/` at `/paradisec-transcripts/` behind the
shared workshop login.

Two things live only on the server, never in git:

- `.env` with `OPENAI_API_KEY` (copy `.env.example`; the Grainger key is fine).
- `data/` holding the corpus manifests, `*_metadata.csv` as written by the
  notebook, with the transcript text in the `text` column. Copy them with
  `scp nt1_metadata.csv workshops:/volume/summer2026/deploy/paradisec-transcripts/data/`.

Then `deploy/paradisec-transcripts/deploy.sh`. On first start the app embeds
the corpus into a named Docker volume (`transcripts_store`), which takes a
minute or two and is kept across rebuilds. Replace a manifest and restart to
re-index; the app notices the change.

The transcripts are access-conditioned PARADISEC material, included with the
depositor's agreement for the workshop. Keep `data/` out of any public place.
