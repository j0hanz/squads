#!/usr/bin/env python3
import re
from pathlib import Path

# Contract tokens - data table for future pairs (one-line additions)
CONTRACTS = [
    ("skills/request-plan/SKILL.md", "Depth: <sketch|contract|blueprint>"),
    ("skills/receive-plan/SKILL.md", "`Depth:`"),
    ("skills/request-plan/SKILL.md", "#task-nnn-<slugified-title>"),
    ("skills/receive-plan/SKILL.md", "#task-nnn-<slugified-title>"),
    ("skills/request-plan/SKILL.md", "REQ-NNN"),
    ("skills/receive-plan/SKILL.md", "REQ-NNN"),
    ("skills/request-code-review/SKILL.md", "pass number"),
    ("skills/receive-code-review/SKILL.md", "cap re-review at 2"),
]


def slug_heading(heading):
    """Convert markdown heading to slug format."""
    s = re.sub(r"[^a-z0-9 -]", "", heading.lower())
    return s.strip().replace(" ", "-")


def check_frontmatter(file_path, dir_name):
    """Check FRONTMATTER requirements. Returns list of (file_path, detail) tuples."""
    failures = []

    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
    except OSError:
        failures.append((file_path, "cannot read file"))
        return failures

    lines = content.split("\n")

    # Check 1: starts with '---'
    if not lines or lines[0] != "---":
        failures.append((file_path, "does not start with '---'"))

    # Find closing ---
    fm_end = -1
    for i in range(1, len(lines)):
        if lines[i] == "---":
            fm_end = i
            break

    if fm_end == -1:
        failures.append(
            (file_path, "frontmatter not closed (no closing '---')")
        )
        return failures

    frontmatter = "\n".join(lines[1:fm_end])

    # Check 2: 'name:' line with correct value
    name_match = re.search(r"^name:\s*(.+)$", frontmatter, re.MULTILINE)
    if not name_match:
        failures.append((file_path, "missing 'name:' line"))
    else:
        name_value = name_match.group(1).strip()
        if name_value != dir_name:
            failures.append(
                (
                    file_path,
                    f"name '{name_value}' does not match dir '{dir_name}'",
                )
            )

    # Check 3-5: 'description:' line
    desc_match = re.search(r"^description:\s*(.+)$", frontmatter, re.MULTILINE)
    if not desc_match:
        failures.append((file_path, "missing 'description:' line"))
    else:
        desc_value = desc_match.group(1).strip()

        # Check 3: starts with 'Use when' — skip for non-invocable skills
        # (router skills injected by hook are never triggered by description)
        invocable = not re.search(
            r"^user-invocable:\s*false\s*$", frontmatter, re.MULTILINE
        )
        if invocable and not desc_value.startswith("Use when"):
            failures.append(
                (file_path, "description does not start with 'Use when'")
            )

        # Check 4: length <= 500
        if len(desc_value) > 500:
            failures.append(
                (
                    file_path,
                    f"description is {len(desc_value)} chars (max 500)",
                )
            )

        # Check 5: NOT wrapped in quotes
        if (desc_value.startswith('"') and desc_value.endswith('"')) or (
            desc_value.startswith("'") and desc_value.endswith("'")
        ):
            failures.append((file_path, "description is wrapped in quotes"))

    return failures


def get_markdown_headings(file_path):
    """Extract all markdown headings and their slugs from a file."""
    headings = {}
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()

        for match in re.finditer(r"^#+\s+(.+)$", content, re.MULTILINE):
            heading_text = match.group(1).strip()
            slug = slug_heading(heading_text)
            headings[slug] = heading_text
    except OSError:
        pass

    return headings


def check_relative_links(file_path):
    """Check RELATIVE LINKS requirements. Returns (failures, check_count)."""
    failures = []
    checks = 0

    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return [(file_path, "cannot read file")], 0

    # Find all links like ](../<dir>/SKILL.md or ](../<dir>/SKILL.md#<anchor>)
    pattern = r"\]\(\.\./([^/]+)/SKILL\.md(?:#([^\)]+))?\)"

    for match in re.finditer(pattern, content):
        target_dir = match.group(1)
        anchor = match.group(2)

        target_file = f"skills/{target_dir}/SKILL.md"
        target_path = Path(target_file)

        # Check if target file exists
        checks += 1
        if not target_path.exists():
            failures.append(
                (file_path, f"link to {target_file} (file does not exist)")
            )
            continue

        # Check anchor if present
        if anchor:
            checks += 1
            headings = get_markdown_headings(target_path)
            if anchor not in headings:
                failures.append(
                    (
                        file_path,
                        f"link to {target_file}#{anchor} (anchor not found)",
                    )
                )

    return failures, checks


def check_contracts():
    """Check CONTRACT TOKENS requirements."""
    failures = []

    for file_path, token in CONTRACTS:
        full_path = Path(file_path)

        if not full_path.exists():
            failures.append((file_path, "file does not exist"))
            continue

        try:
            with open(full_path, encoding="utf-8") as f:
                content = f.read()
        except OSError:
            failures.append((file_path, "cannot read file"))
            continue

        if token not in content:
            failures.append((file_path, f"missing contract token: {token}"))

    return failures


def main():
    skills_dir = Path("skills")

    if not skills_dir.exists():
        print("FAIL skills: directory not found")
        return 1

    all_failures = []
    check_count = 0

    # A. FRONTMATTER checks (5 per file)
    for skill_dir in sorted(skills_dir.iterdir()):
        if not skill_dir.is_dir():
            continue

        skill_file = skill_dir / "SKILL.md"
        skill_file_path = str(skill_file).replace("\\", "/")

        if not skill_file.exists():
            all_failures.append((skill_file_path, "file does not exist"))
            continue

        check_count += 5
        fm_failures = check_frontmatter(skill_file_path, skill_dir.name)
        all_failures.extend(fm_failures)

    # B. RELATIVE LINKS checks (variable per file)
    for skill_file in sorted(skills_dir.glob("*/SKILL.md")):
        skill_file_path = str(skill_file).replace("\\", "/")
        link_failures, link_checks = check_relative_links(skill_file_path)
        check_count += link_checks
        all_failures.extend(link_failures)

    # C. CONTRACT TOKENS checks (1 per token)
    check_count += len(CONTRACTS)
    contract_failures = check_contracts()
    all_failures.extend(contract_failures)

    # Output
    if all_failures:
        for file_path, detail in all_failures:
            print(f"FAIL {file_path}: {detail}")
        return 1
    print(f"OK: {check_count} checks passed")
    return 0


if __name__ == "__main__":
    exit(main())
