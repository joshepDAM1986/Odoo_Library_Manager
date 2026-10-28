# Odoo Library Manager

Odoo 17 module to manage a small library: books, authors, categories, members and loans, with a home dashboard built with OWL.

Built as a learning project to practise Odoo development (ORM, views, security, inheritance, OWL, testing).

## Features

- **Books**: title, ISBN, publication year, pages, author, categories and status (available / borrowed / lost). Kanban view grouped by status, *Mark as Lost* / *Recover* buttons with validation, loans smart button and chatter tracking. Borrow / Return are done through loans.
- **AI category suggestion**: a button asks an LLM (Anthropic API) to pick existing categories from the book title, author and description. The API key lives in a system parameter, never in the code (see below).
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

1. Settings > Technical > System Parameters (developer mode).
2. Create `library_manager.anthropic_api_key` with your API key.
3. Optional: `library_manager.ai_model` to choose the model (default `claude-haiku-5-5`).

The book title, author and description are sent to the external API when the button is pressed.

## Roadmap

- Late-return penalties (suspend members automatically).
- Cron job to remind about overdue loans.
- Record rules / multi-company support.
- Translations (i18n).

## Notes

- Target version: **Odoo 17.0**. Syntax differs from other versions (for example, list views are `<list>` from Odoo 18).
- License: LGPL-3.
