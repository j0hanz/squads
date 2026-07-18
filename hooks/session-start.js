import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const skillPath = path.join(__dirname, '..', 'skills', 'using-squads', 'SKILL.md');

console.log(
  "Skill names below invoke via the Skill tool as 'squads:<name>' (e.g. /dispatch-agents -> squads:dispatch-agents).\n",
);

try {
  if (fs.existsSync(skillPath)) {
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
      process.stdout.write('<squads-router>\n');
      process.stdout.write(cleaned);
    }
  } else {
    console.error(`Error reading squads router skill: ${skillPath} not readable`);
  }
} catch (err) {
  console.error(`Error reading squads router skill: ${err.message}`);
}

console.log('\n</squads-router>');
