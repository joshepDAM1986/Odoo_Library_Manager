# Odoo Library Manager

Odoo 17 module to manage a small library: books, authors, categories, members and loans, with an OWL home dashboard, a PDF report, an optional AI category suggestion and book metadata autofill from Open Library.

Built as a learning project to practise Odoo development (ORM, views, security, inheritance, OWL, QWeb and testing).

## Screenshots

<p>
  <img src="docs/screenshots/dashboard.png" alt="Home dashboard" width="300">
  <img src="docs/screenshots/books-kanban.png" alt="Books kanban" width="300">
</p>
<p>
  <img src="docs/screenshots/loan-form.png" alt="Loan form" width="300">
  <img src="docs/screenshots/partner-library.png" alt="Library tab in contacts" width="300">
</p>

## Features

- **Books**: title, ISBN, optional Open Library work/edition ID, publication year, pages, author, categories, cover image and status (available / borrowed / lost).
  - Catalog-style kanban view (cards with cover thumbnails and a colour status label), plus list and form views.
  - Side filter panel (status and categories, with counters) to browse large catalogs.
  - *Mark as Lost* / *Recover* buttons with validation, loans smart button and chatter tracking. Borrow / Return are done through loans.
- **AI category suggestion**: a button asks the Google Gemini API to pick up to three **existing** categories from the book title, author, year and description (see [Enable the AI suggestion](#enable-the-ai-suggestion)).
- **Book autofill (Open Library)**: enter an ISBN or an Open Library ID (`OL…M` edition or `OL…W` work), then use **Autofill from ISBN or Open Library ID** in the book form's top header. It completes empty book fields and refreshes author metadata when available. Librarians can queue a refresh for selected books from the list view.
- **Authors**: biography, birth date, Open Library ID, book counter (smart button), total pages written, an **Autofill from Open Library** button and a **Print PDF** button for the author sheet. Librarians can queue refreshes for selected authors from the list view.
- **Categories**: colour tags, many-to-many with books.
- **Members**: each member is linked to a contact (`res.partner`) through delegation inheritance (`_inherits`), so the member's **DNI/NIF is the contact's Tax ID (`vat`)** and is unique among library members. Demo members include fictitious DNI values with valid check letters. An existing contact can be turned into a member from the contact list/form (*Action > Create library member*) without duplicating it; enter the DNI/NIF on the contact first or on the member form afterwards. Automatic member number (`LM0001`), status (active / suspended) with Suspend / Activate buttons, archiving, loans smart button, and suspended members shown as *(Suspended)* in every dropdown.
- **Contacts (`res.partner`) extended** with `_inherit` and an XPath view inheritance: smart button and *Library* tab showing the contact's memberships.
- **Loans**: automatic reference (`LN0001`), book, member, loan / due / return dates (due date defaults to the configured loan period, 14 days by default) and status (draft / ongoing / returned / cancelled / lost).
  - *Confirm* checks that the member is active and borrows the book.
  - *Return* gives the book back and stores the return date.
  - *Cancel* releases the book if the loan was ongoing.
  - *Lost*: marking a book as lost closes its ongoing loan as `lost` (final state, kept as history of who had it). The book cannot then be returned or cancelled through that loan.
  - Date constraints: the due date and the return date cannot be earlier than the loan date (the same date is allowed).
  - Only draft loans can be deleted (`@api.ondelete`); the rest are history.
  - Computed *days overdue*, overdue warning in the form and an *Overdue* filter.
  - A daily scheduled job queues one overdue email per loan for members with an email address. Changing the due date re-arms the notice.
  - A second daily job **suspends members with an overdue loan** (even without an email), and marking a book as lost suspends the member who had it. The reason is logged in the member's chatter. A suspended member cannot borrow but can still return books.
  - **Reactivation is always manual** (*Activate* button): recovering a book does not reactivate the member, since a replacement copy does not forgive the member. If a member is reactivated while still holding an overdue loan, the next run suspends them again.
- **PDF report** (QWeb): author sheet with their books.
- **Home dashboard** (OWL client action, with SCSS): counters for books, members and loans (including overdue loans). Each card opens the matching list, already filtered.
- **Statistics** (read-only SQL-view model `library.loan.report`, graph and pivot views): loans per month, most borrowed books, most read authors, most active readers, loans by status and a pivot analysis. Popularity reports default to the top 10 and offer Top 5 / 10 / 20 / 50 filters.
- **Menus** as top-bar tabs: Home, Books, Authors, Members, Loans, Statistics and a Configuration dropdown (Categories).
- **Settings screen** (*Settings > Library*): Gemini API key and model, default loan period and days of grace before suspending. The key and model keep the same system-parameter names, so existing installations need no migration.
- **Security**: two groups, *Library: Reader* (read only) and *Library: Librarian* (full access, includes contact management).
- **Demo data**: categories, authors, books, members and ~60 historical loans spread over the last months (so the statistics have something to show). It is only loaded in databases created with demo data.

## Overdue email notifications

Odoo checks overdue loans once a day. When an ongoing loan has passed its due date, it queues one email for the member, provided the member has an email address. The email is sent on the due date and does not wait for the grace period: the grace period only delays the automatic suspension (*Settings > Library*). A loan remains in the `ongoing` state; overdue is determined from its due date. The notification timestamp is stored on the loan so the daily job does not send duplicates (it is reset if the due date changes). The scheduled action is defined with `numbercall = -1`; without it Odoo 17 would run it once and then deactivate it. The email template is written in English and rendered in the member's language, so it can be translated like the rest of the module.

Configure an outgoing mail server in Odoo (Settings > Technical > Outgoing Mail Servers) and make sure the mail queue is running. Loans without a member email are skipped and can be notified later if an address is added.

## Structure

```
library_manager/
├── __manifest__.py
├── models/        author, book, category, member, loan, res_partner, loan_report (SQL view), res_config_settings
├── views/         views (incl. kanban and res.partner inheritance), actions and menus
├── report/        QWeb PDF report
├── security/      groups and access rules
├── data/          sequences, scheduled job, mail template and demo data
├── migrations/    data migrations between module versions
├── i18n/          translations (Spanish: `es.po`)
├── static/src/dashboard/   OWL component, template and styles
├── docs/          functional specification and screenshots
│   └── screenshots/
└── tests/         automated tests
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
- Reporting with a SQL-view model (`_auto = False`), graph and pivot views, window functions (`RANK`) for top-N rankings.
- `TransactionCase` tests, including mocking an external API.
- Calling an external API with the key stored in `ir.config_parameter`.
- A standard Odoo settings screen (`res.config.settings`) with `config_parameter` fields and the *Settings* app block.
- A public API without a key (Open Library), ISBN-10/13 check-digit validation and downloading an image.

From an author form, librarians can use **Autofill from Open Library** in the header to refresh the author's name, birth date and biography. It uses the saved Open Library ID or searches for an exact normalized author name or alias; if the search is ambiguous, enter the correct ID on the author record and retry.

To refresh existing records, select books or authors in their list views and use **Queue Open Library Refresh**. You can select all books from the list view. The background job processes up to ten records per minute; results and failures appear under **Library > Configuration > Open Library Refreshes**. Book refreshes replace fields when Open Library returns newer values; authors are updated in the same way. Books without an ISBN or Open Library ID are skipped.

## Installation and development

This repository contains the addon only; it does not include an Odoo server, PostgreSQL instance, or Docker Compose configuration. Use an Odoo 17.0 installation and PostgreSQL, and make sure the parent directory of `library_manager` is included in Odoo's `addons_path`. Install the Python dependency declared by the manifest (`requests`) in the Python environment used by Odoo.

Restart the Odoo service after Python changes, then update the module from Apps or with:

```bash
odoo -d YOUR_DB -u library_manager --stop-after-init
```

Use `-i library_manager` instead of `-u` for a first CLI installation. Enable demo data when creating the database if you want the sample catalog and historical loans. After changing JavaScript, hard-refresh the browser (Ctrl+Shift+R).

To run the automated suite, use a separate test database:

```bash
odoo -d test_library -i library_manager \
    --test-enable --test-tags /library_manager --stop-after-init
```

Once `test_library` exists, use `-u` instead of `-i`. The tests that simulate API failures mute the module's logger.

## Enable the AI suggestion

The feature uses the **Google Gemini API** (REST `generateContent`). It is optional: without a key the button shows a clear message and nothing else is affected.

1. Create a Gemini API key in [Google AI Studio](https://aistudio.google.com/apikey).
2. In Odoo, open **Settings > Library**.
3. Paste the key in **Gemini API Key** and save.
4. Optional: set **Gemini Model** to choose another model. The default is `gemini-3.5-flash-lite`; check in [Google's model list](https://ai.google.dev/gemini-api/docs/models) and [pricing](https://ai.google.dev/gemini-api/docs/pricing) that it is available for your project.
5. Open a book and press **Suggest Categories (AI)**.

The screen stores the values in the existing system parameters (`library_manager.gemini_api_key` and `library_manager.gemini_model`), so they can also be edited from *Settings > Technical > System Parameters*.

Notes:

- The book title, author, year and description are sent to Google when the button is pressed. The model can only choose among the categories that already exist in Odoo, and matches are **added** without removing the book's current categories.
- Only librarians can use the feature: the button is hidden for readers and the server also checks the group, so it cannot be triggered through RPC.
- The key is sent in the `x-goog-api-key` header (never in the URL) and must never be committed to Git.
- Free-tier usage is limited, and Google's terms for unpaid usage allow submitted content to be used to improve its products. Do not use it with real customer data.
- HTTP 404 usually means the model is not available for your key (change **Gemini Model** in *Settings > Library*); HTTP 429 means a quota or rate limit was reached.

## Autofill from ISBN or Open Library ID

The **Autofill from ISBN or Open Library ID** button in the book form's top header completes a book from [Open Library](https://openlibrary.org/). It needs no key or configuration. Open Library has separate identifiers for a work (`OL…W`) and a specific edition (`OL…M`); the field accepts either one.

1. Open a book (or press *New*).
2. Enter either an ISBN or the Open Library ID in its field.
3. Press **Autofill from ISBN or Open Library ID** in the form header.

When both fields are filled, the Open Library ID takes precedence. ISBN lookup validates its check digit (ISBN-10 or ISBN-13) and stores the corresponding edition ID when returned. Edition-ID lookup also fills an ISBN when Open Library provides a valid one and no other book already uses it. A work ID can represent many editions, so it does not choose an arbitrary edition ISBN. The action fills empty book fields from the selected record; for a new unsaved book it creates the record with the fetched title and reopens the form. If Open Library provides an author record, the matching author is updated with its current name, birth date and biography, even when those author fields already have values. The book's Open Library ID is stored on the book.

Notes:

- Only librarians can use it: the button is hidden for readers and the server checks the group too.
- The Open Library ID can be shared by multiple book records, which lets separate physical copies reference the same work.
- The author is matched by Open Library ID first, then by normalized name and returned aliases; it is created only when there is no match. If several local authors match, autofill stops with an explanation instead of creating another ambiguous duplicate; resolve the duplicate author records and retry. Only the first author is used, because a book stores a single author.
- For an existing author whose name does not match Open Library's name or aliases, enter the author's Open Library ID in the author form once. Future ISBN autofills will match that record by ID.
- The cover is downloaded when it is an image of at most 5 MB. If the download fails, the rest of the data is still filled and the notification warns about it.
- Open Library is a free service without availability guarantees, and its data may be incomplete or differ from the printed edition. The ISBN endpoint does not return a description; a work ID may provide one.

## Roadmap

- Timed suspensions that expire by themselves.
- Record rules / multi-company support.
- Translations to other languages. The source strings are in English; export a template with `odoo --modules=library_manager --i18n-export=xx.po -l xx_XX`.

## Notes

- Target version: **Odoo 17.0**. Syntax differs from other versions (for example, list views are `<list>` from Odoo 18).
- License: LGPL-3.
- Keep `odoo.conf` (with its `admin_passwd`) outside the module and out of version control; use an `odoo.conf.example` as a template.
