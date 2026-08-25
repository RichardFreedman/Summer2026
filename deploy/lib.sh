# Shared by the deploy scripts. Source, don't run.
#
# The server holds a git clone of this repo at $REMOTE_ROOT. Deploying means
# pulling the wanted branch there and rebuilding the relevant compose stack.
# .env files and other ignored files on the server are never touched.

HOST="${DEPLOY_HOST:-workshops}"
BRANCH="${DEPLOY_BRANCH:-main}"
REMOTE_ROOT="/volume/summer2026"

remote_update_checkout() {
  ssh "$HOST" "cd $REMOTE_ROOT && \
    git fetch -q origin && \
    git checkout -q $BRANCH && \
    git pull -q --ff-only origin $BRANCH && \
    echo \"server at \$(git rev-parse --short HEAD) on \$(git branch --show-current)\""
}
