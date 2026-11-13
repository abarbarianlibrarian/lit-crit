# Literary Criticism website

This repository builds a public website from the **Literary Criticism** Airtable base:
a page for every term, author, work, prize, period and tag, all cross-linked, plus search.

Airtable stays the place you edit. The site rebuilds itself every morning, and you can
rebuild it any time from the **Actions** tab → **Build site from Airtable** → **Run workflow**.

## What's on the site

The menu has three parts: **Home**, **Reference** (Terms, Sets, Authors, Works, Poems and passages, Reading lists,
Periods, Prizes) and **Study** (Study home, Practice tests, Quick quiz, Essay prompts, Flashcards, this year's
reading list, Resources). The home page shows the term and author of the day, then a door into each.

- **Study home** (`/study/`): countdown to the next contest date, flashcards due, practice-test progress,
  "Pick up where you left off", and this year's reading list. Contest dates are `CONTEST_DATES` near the top
  of the Modes section in `build.py`: update them every school year.
- **Quick quiz** (`/study/quiz/`): 10, 20 or 30 random released questions, filtered by part, set, period,
  reading list, test years, or only ones the student missed before. Term, author, work and poem pages link to it
  with **Quiz me**.
- **Examples** (the Examples table) show under the term of the day (up to four) and on each term page.
- On term, author, work and poem pages the practice questions are folded into one box that opens on request.
- The Tags table is called **Sets** on the site, at `/sets/`. Old `/tags/` addresses forward to the matching `/sets/` page.

| Airtable table | On the site |
|---|---|
| Terms | A page per term. Words in CAPITALS in a definition become links to that term. Shows related terms, terms it mentions, terms that mention it, authors, tags and periods. |
| Authors | Portrait, dates, nationality, works, prizes, groups, periods, and terms they appear in. |
| Works | Cover, author, dates, synopsis, prizes, terms and reading resources. |
| Prizes | Grouped by prize, newest first. |
| Historical Periods | By region in order, with previous/next period links. |
| Tags | Term lists with Quizlet, Gimkit, Blooket and Sporcle links. |
| Reading Resources | Grouped by work, linking to each resource's **Link**. Attached files are not copied to the site. |
| Tests and Questions | A page per test with its questions grouped by part. Answers stay hidden until "Show answer" is clicked. Term, author, work and poem pages list the questions that mention them. |
| Poems and Passages | Full text, author, the tests it appeared on, its essay prompts and its questions. |
| Essay Prompts | A page per prompt with its text, and a box where students write their essay (bold, italic, underline, word count). Essays save as they type: in the browser, and in the student's account when signed in. The Essay prompts list marks the ones a student has written. |
| Reading Lists | One table of each school year's novel, play and poet. |
| (Flashcards) | Spaced-repetition decks built from the tables above: all terms, terms by tag, authors → works and works → author (all, or just those on past tests), and prize winners. Students can also make their own decks with the **Add to flashcards** button on any term, author, work or prize page. |

Attached files (test PDFs, reading list files, essay scoring guides) are not published.

**Members** and **Requests** are never published.

## Flashcards

Cards come from each term's **Short Definition**, each author's works, each work's author, and each prize's winners,
so editing those in Airtable updates the cards on the next build. Students grade each card Again, Hard, Good or Easy,
and the site schedules when it comes back (like Anki). Schedules and custom decks are kept in the student's browser,
and in their account when they're signed in. Nothing about flashcards is stored in Airtable.

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

## Weekly backup

Every Sunday, **Weekly Airtable backup** saves every table except Members and Requests
(including tables added later) into the `backup/` folder:
a `.json` file (complete, for restoring) and a `.csv` file (opens in any spreadsheet)
for each table, plus author portraits and book covers in `backup/images/`.
Every week's version is kept in the repository's history.
Members and Requests are never backed up. Attached files other than portraits and covers are not copied.
The table structure (field types, choices, links) is saved in `backup/schema.json`.
To back up right away: Actions tab → **Weekly Airtable backup** → **Run workflow**.
