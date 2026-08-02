# Post-merge ticket hygiene (Integral)
#
# Run after a PR merges to main (agent must run this when the human asks to merge).
# Usage:
#   .\scripts\post_merge_hygiene.ps1 -Issue 68 -PR 69
#   .\scripts\post_merge_hygiene.ps1 -Issue 68
#   .\scripts\post_merge_hygiene.ps1 -PR 69

param(
    [int]$Issue = 0,
    [int]$PR = 0
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw "gh CLI is required"
}

$issueNumbers = New-Object System.Collections.Generic.List[int]
if ($Issue -gt 0) {
    [void]$issueNumbers.Add($Issue)
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
    foreach ($ref in @($prState.closingIssuesReferences)) {
        if ($null -ne $ref.number) {
            $n = [int]$ref.number
            if (-not $issueNumbers.Contains($n)) {
                [void]$issueNumbers.Add($n)
            }
        }
    }
}

if ($issueNumbers.Count -eq 0) {
    Write-Warning "No issue numbers to close. Pass -Issue N and/or ensure the PR body has Closes #N."
}
else {
    foreach ($n in $issueNumbers) {
        $state = gh issue view $n --json state,title | ConvertFrom-Json
        if ($state.state -eq "CLOSED") {
            Write-Host "OK  #$n already CLOSED - $($state.title)"
            continue
        }
        Write-Host "Closing #$n - $($state.title)"
        if ($PR -gt 0) {
            $comment = "Closed after PR #$PR merged to main (post-merge hygiene)."
        }
        else {
            $comment = "Closed after merge to main (post-merge hygiene)."
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
