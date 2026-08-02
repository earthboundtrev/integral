# Post-merge ticket hygiene (Integral)
#
# Run after a PR merges to main (agent must run this when the human asks to merge).
# Usage:
#   .\scripts\post_merge_hygiene.ps1 -Issue 68 -PR 69
#   .\scripts\post_merge_hygiene.ps1 -Issue 68          # issue-only verify/close + prune
#   .\scripts\post_merge_hygiene.ps1 -PR 69             # infer closing issues from the PR

param(
    [int]$Issue = 0,
    [int]$PR = 0
)

$ErrorActionPreference = "Stop"

function Assert-Gh {
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        throw "gh CLI is required"
    }
}

Assert-Gh

$issueNumbers = @()
if ($Issue -gt 0) {
    $issueNumbers += $Issue
}

if ($PR -gt 0) {
    $prState = gh pr view $PR --json state,mergedAt,closingIssuesReferences | ConvertFrom-Json
    if ($prState.state -eq "OPEN") {
        Write-Host "Merging PR #$PR with --delete-branch..."
        gh pr merge $PR --merge --delete-branch
        $prState = gh pr view $PR --json state,mergedAt,closingIssuesReferences | ConvertFrom-Json
    }
    if ($prState.state -ne "MERGED") {
        throw "PR #$PR is $($prState.state); expected MERGED"
    }
    foreach ($ref in $prState.closingIssuesReferences) {
        if ($ref.number) { $issueNumbers += [int]$ref.number }
    }
}

$issueNumbers = $issueNumbers | Select-Object -Unique
if (-not $issueNumbers -or $issueNumbers.Count -eq 0) {
    Write-Warning "No issue numbers to close. Pass -Issue N and/or ensure the PR body has Closes #N."
} else {
    foreach ($n in $issueNumbers) {
        $state = gh issue view $n --json state,title | ConvertFrom-Json
        if ($state.state -eq "CLOSED") {
            Write-Host "OK  #$n already CLOSED — $($state.title)"
            continue
        }
        Write-Host "Closing #$n — $($state.title)"
        $comment = if ($PR -gt 0) {
            "Closed after PR #$PR merged to main (post-merge hygiene)."
        } else {
            "Closed after merge to main (post-merge hygiene)."
        }
        gh issue close $n --reason completed --comment $comment
    }
}

Write-Host "Pruning stale remote-tracking refs..."
git fetch --prune origin

Write-Host "Remote branches (expect mainly origin/main):"
git branch -r

Write-Host "Open issues (expect empty unless new work):"
gh issue list --state open --limit 20

Write-Host "Done."
