Run the full pre-release pipeline in this exact order:

1. Act as .claude/skills/tester.md
   - Check test coverage of recently changed files
   - Add missing tests if found
   - Run pytest tests/ -v — must be all green before continuing

2. Act as .claude/skills/reviewer.md
   - Review recently changed files against the checklist
   - Fix any critical or major issues found
   - Run pytest tests/ -v again after fixes

3. Act as .claude/skills/critic.md
   - Identify top 3 production risk scenarios
   - Fix any high likelihood + high impact issues

4. If all clear:
   - Bump patch version in pyproject.toml and src/deuscode/__init__.py
   - rm -rf dist/ && python -m build
   - python -m twine upload dist/*
   - git add . && git commit -m "release: vX.X.X"
   - git tag vX.X.X
   - gh repo sync
   - gh release create vX.X.X --title "vX.X.X" --notes "Changes in this release"
