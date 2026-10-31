# Literary Criticism website

This repository builds a public website from the **Literary Criticism** Airtable base:
a page for every term, author, work, prize, period and tag, all cross-linked, plus search.

Airtable stays the place you edit. The site rebuilds itself every morning, and you can
rebuild it any time from the **Actions** tab → **Build site from Airtable** → **Run workflow**.

## What's on the site

| Airtable table | On the site |
|---|---|
| Terms | A page per term. Words in CAPITALS in a definition become links to that term. Shows related terms, terms it mentions, terms that mention it, authors, tags and periods. |
| Authors | Portrait, dates, nationality, works, prizes, groups, periods, and terms they appear in. |
| Works | Cover, author, dates, synopsis, prizes, terms and reading resources. |
| Prizes | Grouped by prize, newest first. |
| Historical Periods | By region in order, with previous/next period links. |
| Tags | Term lists with Quizlet, Gimkit, Blooket and Sporcle links. |
| Reading Resources | Grouped by work, linking to each resource's **Link**. Attached files are not copied to the site. |

**Members** and **Requests** are never published.

## Settings

- **Site name:** Settings → Secrets and variables → Actions → **Variables** tab → add `SITE_TITLE`.
- **Airtable access:** the `AIRTABLE_TOKEN` secret (Settings → Secrets and variables → Actions).
  It needs only `data.records:read` on the Literary Criticism base.
- **Rebuild time:** the `cron` line in `.github/workflows/build.yml` (times are UTC).

## Things to know

- If you rename a table's primary field value (a term's name, say), that page's web address changes.
- The site uses Airtable field IDs, so renaming a *field* in Airtable is safe. Deleting a field
  the site uses just makes that detail disappear from the pages.
- Images are copied into the site at build time, because Airtable's own image links expire after a few hours.
