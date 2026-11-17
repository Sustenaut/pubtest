#!/usr/bin/env bash
# Sets up what pubtest's first release needs outside the repository: the
# dependency graph, the release key backed up in Bitwarden, SonarQube Cloud and its SONAR_TOKEN,
# the release app's organization secrets, and then the rulesets. Run it from
# a checkout that holds the release key in corpus/.publet (~/git/pubtest),
# signed in to gh as an owner of Sustenaut:
#
#   scripts/go-live.sh
#
# Each step says what it does and asks first; a step already done is
# skipped, and the first error stops it. It prints no secret: tokens are read
# at hidden prompts and go to gh and Bitwarden on standard input.
set -euo pipefail
root="$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
cd "$root"
owner=Sustenaut
repo=pubtest
slug="$owner/$repo"
sonar_org=sustenaut
sonar_key="${owner}_${repo}"
sonar=https://sonarcloud.io

step() { printf '\n== %s\n' "$*"; }
skip() { echo "   already done: $*"; }
ask() {
  local answer
  read -r -p "   $1 [y/N] " answer </dev/tty
  [[ $answer =~ ^[Yy] ]] || { echo "Stopped; run scripts/go-live.sh again to go on."; exit 1; }
}
secret() {
  local value
  read -r -s -p "   $1: " value </dev/tty
  echo >&2
  [ -n "$value" ] || { echo "   nothing given; stopped." >&2; exit 1; }
  printf '%s' "$value"
}

step "0. The dependency graph, which the review job's dependency review reads"
if gh api "repos/$slug/dependency-graph/sbom" >/dev/null 2>&1; then
  skip "$slug has a dependency graph"
else
  ask "Turn on $slug's dependency graph (with Dependabot alerts)?"
  gh api -X PUT "repos/$slug/vulnerability-alerts" >/dev/null
fi

step "1. Back up the release key (corpus/.publet/signing.key) to Bitwarden as pub-signing-key-$repo"
[ -f corpus/.publet/signing.key ] || { echo "   no corpus/.publet/signing.key here: run this in the checkout that made it"; exit 1; }
tag=$(gh release view --repo "$owner/pubsec" --json tagName -q .tagName)
pubsec=(uvx --from "https://github.com/$owner/pubsec/releases/download/$tag/pubsec-${tag#v}-py3-none-any.whl" pubsec)
if "${pubsec[@]}" signing-key backup --dry-run 2>&1 | grep -q "already"; then
  skip "pub-signing-key-$repo is in Bitwarden"
else
  "${pubsec[@]}" signing-key backup --dry-run
  ask "Write it to Bitwarden (pubsec asks for a token that may write to project Pub)?"
  "${pubsec[@]}" signing-key backup
fi

step "2. SonarQube Cloud: the project $sonar_key, Automatic Analysis off, and its token as SONAR_TOKEN"
if gh secret list --repo "$slug" --json name -q '.[].name' | grep -qx SONAR_TOKEN; then
  skip "$slug has SONAR_TOKEN"
else
  echo "   A SonarQube Cloud token of yours (My Account, Security) that may administer the $sonar_org organization."
  token=$(secret "SonarQube Cloud token")
  sonar_api() { curl -fsS -u "$token:" "$@"; }
  if sonar_api "$sonar/api/projects/search?organization=$sonar_org&projects=$sonar_key" | grep -q "\"key\":\"$sonar_key\""; then
    skip "the project $sonar_key exists"
  else
    ask "Create the project $sonar_key in $sonar_org, public?"
    sonar_api -X POST "$sonar/api/projects/create" -d "organization=$sonar_org" -d "project=$sonar_key" \
      -d "name=$repo" -d visibility=public >/dev/null
  fi
  ask "Turn Automatic Analysis off for $sonar_key (CI's sonar job analyses it)?"
  sonar_api -X POST "$sonar/api/autoscan/activation" -d "projectKey=$sonar_key" -d enable=false >/dev/null
  ask "Set the token as $slug's SONAR_TOKEN?"
  printf '%s' "$token" | gh secret set SONAR_TOKEN --repo "$slug"
  unset token
fi

step "3. The release app's organization secrets, RELEASE_APP_ID and RELEASE_APP_KEY, for $slug"
repo_id=$(gh api "repos/$slug" -q .id)
for name in RELEASE_APP_ID RELEASE_APP_KEY; do
  if gh api "orgs/$owner/actions/secrets/$name/repositories" -q '.repositories[].name' | grep -qx "$repo"; then
    skip "$name reaches $repo"
  else
    ask "Let $repo read the organization secret $name?"
    gh api -X PUT "orgs/$owner/actions/secrets/$name/repositories/$repo_id" >/dev/null
  fi
done
echo "   The sustenaut-release app is installed on every repository of $owner, so nothing more is needed for it."

step "4. Rulesets: ./pubkit protect, once main's CI passes"
if ./pubkit protect --check >/dev/null 2>&1; then
  skip "$slug's rulesets match pubkit.json"
else
  run=$(gh run list --repo "$slug" --branch main --workflow main.yml --limit 1 --json conclusion -q '.[0].conclusion // ""')
  if [ "$run" != success ]; then
    echo "   main's last CI run is '${run:-none}': merge the 0.1 pull request, let main pass, then run this again."
    exit 1
  fi
  ./pubkit protect --check || true
  ask "Put pubkit's rulesets on $slug?"
  ./pubkit protect
fi

step "Done. Next: pubrel prepare in this checkout cuts 0.1.0."
