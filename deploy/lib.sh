# Shared by the deploy scripts. Source, don't run.
#
# The server holds a git clone of this repo at $REMOTE_ROOT, on main.
# Deploying means pulling main there and rebuilding the relevant compose
# stack. .env files and other ignored files on the server are never touched.

HOST="${DEPLOY_HOST:-workshops}"
REMOTE_ROOT="/volume/summer2026"

remote_update_checkout() {
  ssh "$HOST" "cd $REMOTE_ROOT && \
    git checkout -q main && \
    git pull -q --ff-only origin main && \
    echo \"server at \$(git rev-parse --short HEAD)\""
}
