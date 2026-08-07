# Database Concepts

All PostgreSQL and MongoDB study files are flattened directly under this folder.

- `q1.md` through `q100.md` contain the exact original questions.
- `postgresql-questions.md` and `mongodb-questions.md` are the original per-technology indexes.
- `postgresql-README.md` and `mongodb-README.md` are the previous subfolder README summaries.

## Generate concept notes

Use the `generate_concept.py` script to automatically fill in a file with a full concept note.

From `database/concepts/`:

```powershell
python generate_concept.py q1
```

Or use the VS Code prompt command when available:

- `Generate Database Concept Note`

Provide the file name only, for example `q1.md` or `q51`.
