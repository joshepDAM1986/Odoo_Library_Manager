# Odoo Library Manager

Odoo 17 module to manage a small library: books, authors, categories, members and loans, with a home dashboard built with OWL.

Built as a learning project to practise Odoo development (ORM, views, security, inheritance, OWL, testing).

## Features

- **Books**: title, ISBN, publication year, pages, author, categories and status (available / borrowed / lost). Status buttons (Borrow, Return, Mark as Lost, Recover) with validation, and chatter tracking.
- **Authors**: biography, birth date, book counter (smart button) and total pages written.
- **Categories**: colour tags, many-to-many with books.
- **Members**: each member is linked to a contact (`res.partner`) through delegation inheritance (`_inherits`). Automatic member number (`LM0001`), status (active / suspended) with Suspend / Activate buttons, and archiving.
- **Loans**: automatic reference (`LN0001`), book, member, loan / due / return dates and status (draft / ongoing / returned).
  - *Confirm* checks that the member is active and borrows the book.
  - *Return* gives the book back and stores the return date.
  - Date constraints: the due date and the return date cannot be earlier than the loan date (the same date is allowed).
- **Home dashboard** (OWL client action): counters for books, members and loans (including overdue loans). Each card opens the matching list, already filtered.
- **Menus** as top-bar tabs: Home, Books, Authors, Members, Loans and a Configuration dropdown (Categories).
- **Security**: two groups, *Library: Reader* (read only) and *Library: Librarian* (full access, includes contact management).
- **Demo data**: categories, authors, books and members. It is only loaded in databases created with demo data.

## Structure

```
library_manager/
├── __manifest__.py
├── models/        author, book, category, member, loan
├── views/         views, actions, dashboard action and menus
├── security/      groups and access rules
├── data/          sequences and demo data
├── static/src/dashboard/   OWL component and template
└── tests/         automated tests
```

## Concepts practised

- Relations: `Many2one`, `One2many`, `Many2many`.
- Computed and related fields, `@api.depends`, `@api.constrains`, SQL constraints.
- Inheritance: `_inherit` (mixins such as `mail.thread`) and `_inherits` (delegation to `res.partner`).
- `ir.sequence`, `@api.model_create_multi`, status workflows with buttons.
- Views for Odoo 17 syntax (`<tree>`, `invisible="state != 'draft'"`, no `attrs`), search views and chatter.
- Security groups and `ir.model.access.csv`.
- OWL 2 client action with the `orm` and `action` services.
- `TransactionCase` tests.

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

## Roadmap

- Block deleting loans that are no longer in draft (`@api.ondelete`).
- *Cancelled* loan status that releases the book.
- More tests: loan flow, suspended members, date constraints, member numbering.
- Late-return penalties based on the difference between the due date and the return date.
- QWeb PDF report (author sheet with its books).
- Cron job to flag overdue loans.
- Visual improvements to the dashboard.

## Notes

- Target version: **Odoo 17.0**. Syntax differs from other versions (for example, list views are `<list>` from Odoo 18).
- License: LGPL-3.
