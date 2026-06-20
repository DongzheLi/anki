# Deferred / known issues

Incidental things noticed while building — not blocking, to revisit later.

- **Empty taxonomy isn't pruned.** Categories/topics are find-or-create on item
  add/move, but deleting or moving the last item out of a topic/category leaves
  the (now empty) row behind. It still shows in the editor datalists. TODO:
  prune empty topics/categories, or hide empties from the datalists.

- **Category/topic names are case-sensitive.** "Leetcode" and "leetcode" are
  distinct rows, so a typo silently creates a duplicate. TODO: case-insensitive
  match on find-or-create (or normalise on input).

- **No UI to rename/delete a category or topic anymore.** The flat-table
  redesign dropped the tree CRUD. Renaming currently only happens implicitly by
  editing every item's category/topic. The server still has the
  POST/PATCH/DELETE category/topic routes and the /api/tree endpoint, now unused
  by the client. TODO: decide whether to expose lightweight taxonomy management
  or remove the dead routes.

- **Legacy `items.content` / `content_format` / `language` / `source_filename`
  columns are now dead.** Solutions live in the `solutions` table; these columns
  are only read once, by the one-time backfill migration. TODO: drop them once
  we're confident every DB has been migrated.
