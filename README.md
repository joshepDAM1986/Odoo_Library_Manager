# Odoo Library Manager

Odoo 17 module to manage authors, books and categories.

## Features
- Authors with biography, book counter and total pages written.
- Books with ISBN, publication year, status (available / borrowed / lost) and chatter tracking.
- Categories with colour tags.
- Two security groups: **Library: Reader** (read only) and **Library: Librarian** (full access).
- Demo data: 10 categories, 10 authors, 26 books (only loaded with demo data).

## Install
Put the folder in `extra-addons`, restart Odoo, update the apps list and install *Library Manager*.
After changing Python code: `odoo -u library_manager` (or restart + upgrade from Apps).
