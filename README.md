# 📚 skills

ethanbeau's personal agent skills repository, intended to be symlinked into `~/.agents/skills` or installed via `npx skills`.

## Quick setup

```bash
cd ~/code/projects/skills
bash scripts/setup.sh
```

What `scripts/setup.sh` does:

- Creates `~/.agents/skills`
- Finds each top-level skill directory that contains a `SKILL.md`
- Symlinks each skill into `~/.agents/skills`
- Refreshes existing skill symlinks in place

## Structure

- `git-workflow/` — git workflow skill and helper scripts
- `scripts/setup.sh` — symlink local skills into `~/.agents/skills`

## Notes

- Skills are symlinked into `~/.agents/skills`
- If a target path already exists and is not a symlink, setup stops instead of overwriting it
