---
name: git-branching
description: Initializes local Git repositories, manages branches, creates Git worktrees, and controls release manifests.
---

# Git Branching Skill

## When to Use
Use this skill when initializing project repositories, creating task branches, managing Git worktrees for parallel agent execution, merging verified code, or tagging releases.

## Required Inputs
- Repository target directory (`mock-vendor-api` or `channel-app`).
- Operation type: `init`, `create-branch`, `create-worktree`, `merge`, `tag-release`.
- Branch name or task identifier.

## Execution Steps
1. **Repository Initialization**:
   - Initialize Git repo: `git init`.
   - Set up standard `.gitignore` and default branch `main`.
   - Create initial commit and establish the `develop` branch.
2. **Task Branch Creation**:
   - Create isolated branch: `git checkout -b <branch_name> develop`.
   - Branch naming: `feature/<task>`, `fix/<defect>`, `security/<finding>`, `release/<version>`.
3. **Worktree Management**:
   - For concurrent tasks: `git worktree add <worktree_path> <branch_name>`.
   - Execute task within the worktree directory.
   - Upon completion: commit changes, remove worktree `git worktree remove <worktree_path>`, and prune.
4. **Integration & Release Manifest**:
   - Ensure clean working tree and tests passing before merging into `develop`.
   - When preparing a release: create `release/vX.Y.Z`, verify combined checks, fast-forward merge to `main`, and tag release.
   - Record matching commit hashes in `GitReleaseManifests`.

## Constraints
- No direct commits or pushes to `main`.
- Conventional commit message format is mandatory.
- No cross-repository file operations.

## Verification
- Inspect `git status`, `git branch -a`, and `git log -n 5 --oneline` to verify branch states and history.
- Ensure worktree directories are cleanly pruned after use.

## Expected Outputs
- New Git branch or worktree ready for agent use.
- Clean merge commit into target integration branch.
- Manifest record linking compatible mock and channel commits.
