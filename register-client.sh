#!/usr/bin/env bash
# Gives estimate.sustenaut.eu sign-in with auth.sustenaut.eu's team realm, and its Pages project the two secrets.
# sustenaut.eu has one client for all its team sites, already approved by its DNS record
# (_sustenaut-auth.sustenaut.eu), so this needs no new record: it adds this site's redirect URI and
# declares the role estimate, with Sustenaut/auth's register-app.py, on the server that keeps the client.
# Then it puts the client's secret into the project (it goes through this run's pipes, never on a command
# line or disk here), and a random session key if the project has none.
#
# Run it from the repository root, signed in to Sustenaut's tailnet, once the Pages project exists (Sustenaut/shared-infra's pubkit.json):
#
#   ./with-secrets ./register-client.sh
#
# Needs wrangler (npm ci --ignore-scripts), CLOUDFLARE_GITHUB_API_TOKEN and CLOUDFLARE_ACCOUNT_ID from Bitwarden, and a checkout of
# Sustenaut/auth beside this one (or AUTH=its path). Running it again changes nothing but the client's
# secret in the project, which is the same one.
set -euo pipefail
root="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
host=estimate.sustenaut.eu
domain=sustenaut.eu
auth=${AUTH_REALM_URL:-https://auth.sustenaut.eu/realms/team}
state=/root/.config/sustenaut-auth/team-$domain
server=${SUSTENAUT_SERVER:-sustenaut}
register_app="${AUTH:-$root/../auth}/register-app.py"
wrangler=(npx --no-install wrangler pages secret)
project=sustenaut-estimate

[[ -x "$root/node_modules/.bin/wrangler" ]] || { echo "run npm ci --ignore-scripts first" >&2; exit 1; }
[[ -f "$register_app" ]] || { echo "no $register_app: clone Sustenaut/auth beside this repository or set AUTH" >&2; exit 1; }
for name in CLOUDFLARE_GITHUB_API_TOKEN CLOUDFLARE_ACCOUNT_ID; do
  [[ -n "${!name:-}" ]] || { echo "$name is not set: run this through ./with-secrets, and check it is in Bitwarden." >&2; exit 1; }
done
export CLOUDFLARE_API_TOKEN=$CLOUDFLARE_GITHUB_API_TOKEN

# The script goes on stdin; its sign-in instructions come back on stderr, its result on stdout.
# shellcheck disable=SC2029 # the names are this machine's on purpose
registration="$(ssh "root@$server" "python3 -I - --state-dir $state --auth $auth --domain $domain \
  --name 'sustenaut.eu team sites' --redirect https://$host/oauth2/callback --logout https://$host/ --role estimate" \
  < "$register_app" || true)"
status="$(jq -r .status <<<"$registration" 2>/dev/null || echo error)"
if [[ "$status" != ok && "$status" != registered ]]; then
  echo "The registration did not finish: $registration" >&2
  exit 1
fi
echo "Client $(jq -r .client_id <<<"$registration") ($status): $host's redirect URI is on it, and the role estimate is declared."

# shellcheck disable=SC2029 # the path is this machine's on purpose
ssh "root@$server" "python3 -I -c 'import json,sys; print(json.load(open(sys.argv[1]))[\"client_secret\"], end=\"\")' $state/client.json" |
  "${wrangler[@]}" put CLIENT_SECRET --project-name "$project"
if ! "${wrangler[@]}" list --project-name "$project" | grep -q SESSION_KEY; then
  openssl rand -hex 32 | tr -d '\n' | "${wrangler[@]}" put SESSION_KEY --project-name "$project"
fi
echo "The project has its secrets. They reach the site at its next deploy: run the deploy workflow."
