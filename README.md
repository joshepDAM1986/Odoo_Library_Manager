# Odoo Library Manager

Odoo 17 module to manage a small library: books, authors, categories, members and loans, with a home dashboard built with OWL.

Built as a learning project to practise Odoo development (ORM, views, security, inheritance, OWL, testing).

## Features

- **Books**: title, ISBN, publication year, pages, author, categories and status (available / borrowed / lost). Kanban view grouped by status, *Mark as Lost* / *Recover* buttons with validation, loans smart button and chatter tracking. Borrow / Return are done through loans.
- **AI category suggestion**: a button uses the Google Gemini API to suggest up to three existing categories based on the book title, author and description. The API key is stored in an Odoo system parameter, not in source code.
- **Authors**: biography, birth date, book counter (smart button) and total pages written.
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
- **PDF report** (QWeb): author sheet with their books, available from the *Print* menu on an author.
- **Home dashboard** (OWL client action, with SCSS): counters for books, members and loans (including overdue loans). Each card opens the matching list, already filtered.
- **Menus** as top-bar tabs: Home, Books, Authors, Members, Loans and a Configuration dropdown (Categories).
- **Security**: two groups, *Library: Reader* (read only) and *Library: Librarian* (full access, includes contact management).
- **Demo data**: categories, authors, books and members. It is only loaded in databases created with demo data.

## Structure

```
library_manager/
├── __manifest__.py
├── models/        author, book, category, member, loan
├── views/         views (incl. kanban and res.partner inheritance), actions and menus
├── report/        QWeb PDF report
├── security/      groups and access rules
├── data/          sequences and demo data
├── static/src/dashboard/   OWL component, template and styles
└── tests/         automated tests
```

## Concepts practised

- Relations: `Many2one`, `One2many`, `Many2many`.
- Computed and related fields, `@api.depends`, `@api.constrains`, SQL constraints.
- Inheritance: `_inherit` (mixins such as `mail.thread`, and extending `res.partner`), `_inherits` (delegation to `res.partner`) and view inheritance with XPath.
- `ir.sequence`, `@api.model_create_multi`, status workflows with buttons.
- Views for Odoo 17 syntax (`<tree>`, `invisible="state != 'draft'"`, no `attrs`), search views and chatter.
- Security groups and `ir.model.access.csv`.
- OWL 2 client action with the `orm` and `action` services.
- `TransactionCase` tests, including mocking an external API.
- Kanban views, QWeb reports, calling an external API with the key in `ir.config_parameter`.

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

Python changes need the restart; XML and manifest changes need the update (`-u`). After changing JavaScript, hard-refresh the browser (Ctrl+Shift+R).

## Run the tests

Use a separate database so your real one is not touched:

```bash
docker compose run --rm web odoo -d test_library -i library_manager \
    --test-enable --test-tags /library_manager --stop-after-init --no-http
```

Once `test_library` exists, use `-u` instead of `-i`. A successful run ends with `0 failed, 0 error(s)`.

## Enable the AI suggestion

The original integration used Anthropic (Claude). It was replaced with **Google Gemini** so the feature can work with models offered under the **Gemini API free tier**, without requiring a paid Anthropic API account. Free-tier availability and request limits depend on Google's current pricing, the selected model and the API project; free usage is **not unlimited**.

1. Create a Gemini API key in [Google AI Studio](https://aistudio.google.com/apikey).
2. In Odoo, enable developer mode and open **Settings > Technical > System Parameters**.
3. Create `library_manager.gemini_api_key` and set its value to your API key.
4. Optionally create `library_manager.gemini_model` to select a model supported by your key. The example Python implementation defaults to `gemini-3.5-flash-lite`; **verify that this model is available and has a free tier for your project** before using it. Check [Google's pricing](https://ai.google.dev/gemini-api/docs/pricing) and [available models](https://ai.google.dev/gemini-api/docs/models).
5. Restart Odoo after updating the Python code, then open a book and click the AI category suggestion button.

The book title, author and description (and, in the updated implementation, publication year) are sent to Google's Gemini API only when the button is pressed. Gemini is asked to return up to three names from categories already created in Odoo. Matching categories are added without removing existing ones.

The integration uses the REST `generateContent` endpoint and passes the API key in the `x-goog-api-key` header. Do not commit API keys to Git. If a configured model returns HTTP 404, check the models accessible to your API key and update `library_manager.gemini_model`. HTTP 429 can indicate quota or rate limits.

**Migration from Anthropic:** `library_manager.anthropic_api_key` and `library_manager.ai_model` are no longer read by the updated integration. After confirming Gemini works, remove the obsolete parameters if they are not used elsewhere. If your existing automated tests mock Anthropic requests, update them to mock Gemini's REST response instead.

## Roadmap

- Late-return penalties (suspend members automatically).
- Cron job to remind about overdue loans.
- Record rules / multi-company support.
- Translations (i18n).

## Notes

- Target version: **Odoo 17.0**. Syntax differs from other versions (for example, list views are `<list>` from Odoo 18).
- License: LGPL-3.
