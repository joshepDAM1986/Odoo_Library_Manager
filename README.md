# Odoo Library Manager

Odoo 17 module to manage a small library: books, authors, categories, members and loans, with an OWL home dashboard, a PDF report and an optional AI category suggestion.

Built as a learning project to practise Odoo development (ORM, views, security, inheritance, OWL, QWeb and testing).

## Features

- **Books**: title, ISBN, publication year, pages, author, categories, cover image and status (available / borrowed / lost).
  - Catalog-style kanban view (cards with cover thumbnails and a colour status label), plus list and form views.
  - Side filter panel (status and categories, with counters) to browse large catalogs.
  - *Mark as Lost* / *Recover* buttons with validation, loans smart button and chatter tracking. Borrow / Return are done through loans.
- **AI category suggestion**: a button asks the Google Gemini API to pick up to three **existing** categories from the book title, author, year and description (see [Enable the AI suggestion](#enable-the-ai-suggestion)).
- **Authors**: biography, birth date, book counter (smart button), total pages written and a **Print PDF** button for the author sheet.
- **Categories**: colour tags, many-to-many with books.
- **Members**: each member is linked to a contact (`res.partner`) through delegation inheritance (`_inherits`). Automatic member number (`LM0001`), status (active / suspended) with Suspend / Activate buttons, archiving, loans smart button, and suspended members shown as *(Suspended)* in every dropdown.
- **Contacts (`res.partner`) extended** with `_inherit` and an XPath view inheritance: smart button and *Library* tab showing the contact's memberships.
- **Loans**: automatic reference (`LN0001`), book, member, loan / due / return dates (due date defaults to +14 days) and status (draft / ongoing / returned / cancelled).
  - *Confirm* checks that the member is active and borrows the book.
  - *Return* gives the book back and stores the return date.
  - *Cancel* releases the book if the loan was ongoing.
  - Date constraints: the due date and the return date cannot be earlier than the loan date (the same date is allowed).
  - Only draft loans can be deleted (`@api.ondelete`); the rest are history.
  - Computed *days overdue*, overdue warning in the form and an *Overdue* filter.
- **PDF report** (QWeb): author sheet with their books.
- **Home dashboard** (OWL client action, with SCSS): counters for books, members and loans (including overdue loans). Each card opens the matching list, already filtered.
- **Menus** as top-bar tabs: Home, Books, Authors, Members, Loans and a Configuration dropdown (Categories).
- **Security**: two groups, *Library: Reader* (read only) and *Library: Librarian* (full access, includes contact management).
- **Demo data**: categories, authors, books and members. It is only loaded in databases created with demo data.

## Structure

```
library_manager/
├── __manifest__.py
├── models/        author, book, category, member, loan, res_partner
├── views/         views (incl. kanban and res.partner inheritance), actions and menus
├── report/        QWeb PDF report
├── security/      groups and access rules
├── data/          sequences and demo data
├── static/src/dashboard/   OWL component, template and styles
└── tests/         automated tests (52)
```

## Concepts practised

- Relations: `Many2one`, `One2many`, `Many2many`.
- Computed and related fields, `@api.depends`, `@api.constrains`, SQL constraints.
- Inheritance: `_inherit` (mixins such as `mail.thread`, and extending `res.partner`), `_inherits` (delegation to `res.partner`) and view inheritance with XPath.
- `ir.sequence`, `@api.model_create_multi`, `@api.ondelete`, status workflows with buttons.
- Odoo 17 view syntax (`<tree>`, `invisible="state != 'draft'"`, no `attrs`), kanban, search views, search panel and chatter.
- Security groups and `ir.model.access.csv`.
- OWL 2 client action with the `orm` and `action` services, and SCSS.
- QWeb PDF reports.
- `TransactionCase` tests, including mocking an external API.
- Calling an external API with the key stored in `ir.config_parameter`.

## Install (Docker)

The project runs with Docker Compose (Odoo 17 + PostgreSQL 15). The module lives in `./extra-addons`, mounted at `/mnt/extra-addons`.

```bash
docker compose up -d
```

Open `http://localhost:8069`, create a database (tick *Demo data* if you want the sample records), then install **Library Manager** from Apps.

After changing the code:

```bash
docker compose restart web
docker compose exec web odoo -d YOUR_DB -u library_manager --stop-after-init \
    --db_host=db --db_user=odoo --db_password=odoo --no-http
docker compose restart web
```

Python changes need the restart **before** the update; XML and manifest changes need the update (`-u`). After changing JavaScript, hard-refresh the browser (Ctrl+Shift+R).

## Run the tests

Use a separate database so your real one is not touched:

```bash
docker compose run --rm web odoo -d test_library -i library_manager \
    --test-enable --test-tags /library_manager --stop-after-init --no-http
```

Once `test_library` exists, use `-u` instead of `-i`. A successful run ends with `0 failed, 0 error(s)`. Some `ERROR` log lines are expected: they come from tests that simulate API failures on purpose.

## Enable the AI suggestion

The feature uses the **Google Gemini API** (REST `generateContent`). It is optional: without a key the button shows a clear message and nothing else is affected.

1. Create a Gemini API key in [Google AI Studio](https://aistudio.google.com/apikey).
2. In Odoo, enable developer mode and open **Settings > Technical > System Parameters**.
3. Create `library_manager.gemini_api_key` with your key as the value.
4. Optional: create `library_manager.gemini_model` to choose the model. The default is `gemini-3.5-flash-lite`; check in [Google's model list](https://ai.google.dev/gemini-api/docs/models) and [pricing](https://ai.google.dev/gemini-api/docs/pricing) that it is available for your project.
5. Restart Odoo after changing Python code, open a book and press **Suggest Categories (AI)**.

Notes:

- The book title, author, year and description are sent to Google when the button is pressed. The model can only choose among the categories that already exist in Odoo, and matches are **added** without removing the book's current categories.
- The key is sent in the `x-goog-api-key` header (never in the URL) and must never be committed to Git.
- Free-tier usage is limited, and Google's terms for unpaid usage allow submitted content to be used to improve its products. Do not use it with real customer data.
- HTTP 404 usually means the model is not available for your key (change `library_manager.gemini_model`); HTTP 429 means a quota or rate limit was reached.

## Roadmap

- Late-return penalties (suspend members automatically).
- Cron job to remind about overdue loans.
- Record rules / multi-company support.
- Translations (i18n).

## Notes

- Target version: **Odoo 17.0**. Syntax differs from other versions (for example, list views are `<list>` from Odoo 18).
- License: LGPL-3.
