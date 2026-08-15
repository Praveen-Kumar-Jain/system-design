# Database Concepts

All PostgreSQL and MongoDB study files are flattened directly under this folder. Each file uses a descriptive kebab-case name that reflects the question's intent, such as `postgresql-row-level-security.md` or `mongodb-change-stream-webhooks.md`.

## Generate concept notes

Use the `generate_concept.py` script to automatically fill in a file with a full concept note.

From `database/concepts/`:

```powershell
python generate_concept.py postgresql-row-level-security
```

Or use the VS Code prompt command when available:

- `Generate Database Concept Note`

Provide the file name only, for example `postgresql-row-level-security.md` or `mongodb-change-stream-webhooks`.
