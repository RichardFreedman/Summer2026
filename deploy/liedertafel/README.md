# Liedertafel TEI edition

Static site for the page-by-page TEI edition of the Melbourne Liedertafel's
263rd concert programme (23 October 1899), served at `/liedertafel/` with no
login, since the edition is public.

The site and its source live in `Melbourne_Rare_Concert/liedertafel/`:
`site/index.html` is the self-contained viewer (TEI and facsimile images
embedded) built by `tei/build_viewer.py`, and `site/UDC20260028-21.xml` is the
TEI file itself, for download. This directory only holds the small Caddy that
serves that folder and the compose stack that joins it to the shared proxy.

To update: rebuild as described in that folder's README, commit `site/`, and
run `deploy/liedertafel/deploy.sh`.
