# 📦 How to Release a New Version

## Pre-Release Checklist

- [ ] All changes committed and pushed
- [ ] Tested on at least 2 different PDFs
- [ ] VERSION in robostripper.py matches what you want to release
- [ ] Git tag created (pre-commit hook does this automatically)

## Release Steps

### 1. Push Your Changes

```bash
git push
git push --tags  # ⚠️ Don't forget this! Otherwise GitHub Actions won't build.
```

### 2. Wait for GitHub Actions

- Go to your repo → **Actions** tab
- Wait for the build to complete (~5 minutes)
- You'll see: ✅ build-mac, ✅ build-windows

### 3. Create the GitHub Release

1. Go to your repo → **Releases** → **Draft a new release**

2. **Choose a tag**: Select the tag you just pushed (e.g., `v1.0.1`)

3. **Release title**: `RoboStripper 1.0.1` (match the version)

4. **Description**: Copy/paste from `.github/RELEASE_TEMPLATE.md` and fill in what's new

5. **Attach binaries**:
   - The Mac and Windows builds are attached automatically! ✨
   - Just verify they're there: `RoboStripper`, `RoboStripper.exe`, `robostripper.py`

6. **Publish release** 🎉

### 4. Verify

- Click on your new release
- Make sure all 3 files are there (Mac, Windows, Python)
- Download instructions should be clear
- Test one download to make sure it works

## What Happens Next

- Users opening RoboStripper will see the update notification
- Python users can auto-update with one click
- Binary users will get a link to the download page

## Common Issues

**"No binaries attached to release"**
→ You forgot `git push --tags`. The GitHub Actions workflow only runs on tags.

**"GitHub Actions failed"**
→ Check the Actions tab for error details. Usually a syntax error in robostripper.py.

**"Tag already exists"**
→ You tried to release the same version twice. Bump VERSION and create a new tag.

## Need to Undo?

If you accidentally release the wrong version:

1. Go to Releases → Click the release → **Delete release**
2. Delete the tag: `git tag -d v1.0.1 && git push origin :refs/tags/v1.0.1`
3. Fix the issue, bump version, try again

---

## Quick Reference

**Complete release workflow:**
```bash
# 1. Make changes
git add .
git commit -m "Add new feature"
# Pre-commit hook asks: Bump version? → Y → 1.1.0 → Creates tag

# 2. Push everything
git push && git push --tags

# 3. Go to GitHub → Releases → Draft new release
# 4. Select v1.1.0 tag → Add description → Publish

# Done! 🎉
```
