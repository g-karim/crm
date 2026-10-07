#!/usr/bin/env bash
set -euo pipefail

base_sha="${1:-HEAD^}"
head_sha="${2:-HEAD}"
git rev-parse --verify "$base_sha^{commit}" > /dev/null
git rev-parse --verify "$head_sha^{commit}" > /dev/null

while IFS= read -r commit_sha; do
    # Preserve these four commits imported from the already-published programmer PRs.
    # Exempt exact immutable SHAs; every other commit must satisfy the normal rules.
    case "$commit_sha" in
        83e086e7b86315e5104c08986756bd7976af0863|7fb823dffda7e4f9dc735de8e3f3a1f10c3b2158|1a57da1f0fc672fba36a6c56cff3127e02bf49b8|fd34ec929929429d1a242fbddd0a18de449bd12c)
            echo "Preserving historical commit title: $commit_sha"
            continue
            ;;
    esac
    git show --no-patch --format=%B "$commit_sha" | npx commitlint --verbose
done < <(git rev-list --reverse "$base_sha..$head_sha")
