# Liedertafel TEI edition

Static site for the page-by-page TEI edition of the Melbourne Liedertafel's
263rd concert programme (23 October 1899), served at `/liedertafel/`.

`site/index.html` is a single self-contained viewer (TEI and facsimile images
embedded) built from the `rare_music_workshop` project with
`tei/build_viewer.py`; `site/UDC20260028-21.xml` is the TEI file itself, for
download. To update: rebuild there, copy both files here, commit, and run
`deploy/liedertafel/deploy.sh`.
