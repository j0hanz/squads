import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const skillPath = path.join(__dirname, '..', 'skills', 'using-squads', 'SKILL.md');

try {
  const rawContent = fs.readFileSync(skillPath, 'utf8');

  // Strip YAML frontmatter:
  // It starts with --- and ends with ---
  const cleaned = rawContent.replace(/^---[\s\S]*?---\r?\n/, '');
  if (
    cleaned.includes('<squads-router>') ||
    cleaned.includes('</squads-router>') ||
    cleaned.includes('<system-reminder')
  ) {
    console.error('squads: refusing to inject router content containing reserved sentinels');
  } else {
    console.log(
      "Skill names below invoke via the Skill tool as 'squads:<name>' (e.g. /dispatch-agents -> squads:dispatch-agents).\n",
    );
    process.stdout.write('<squads-router>\n');
    process.stdout.write(cleaned);
    console.log('\n</squads-router>');
  }
} catch (err) {
  console.error(`Error reading squads router skill: ${err.message}`);
}
