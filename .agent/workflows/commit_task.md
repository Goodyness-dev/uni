When the user types /commit_task with a task id:
1. Run the quick check (backend) or the type check and lint (frontend). If it fails, fix first.
2. Show git status. Confirm no .env, no vault data, no database file, no packages folder, no tokens.
3. Stage only files related to the task.
4. Commit with the format "<type>(<area>): <what> [<task id>]" and a body explaining why.
5. Tick the task checkbox in the task file in the same commit.
6. Print the commit hash. Do not push unless asked.
