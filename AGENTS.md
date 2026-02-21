## Skills
A skill is a set of local instructions to follow that is stored in a `SKILL.md` file.
Below is the list of skills available in this repository context.

### Available skills
- acm-codebase-memory: Agent memory for ACM ownership, runtime flow, and output interpretation, backed by generated Obsidian graph notes and syncable references. (file: skills/acm-codebase-memory/SKILL.md)

### How to use skills
- Trigger rule: if a task requires understanding ACM structure, function ownership, runtime sequence, or output semantics, use `acm-codebase-memory` first.
- Refresh memory before major changes:
`python scripts/manage_acm_agent_memory.py refresh --sync-repo-skill --sync-local-skill`
- Run memory health checks when uncertain:
`python scripts/manage_acm_agent_memory.py health`
