
import base64
import json
import logging
import re
import time
from datetime import date

import requests

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


_logger = logging.getLogger(__name__)

GEMINI_BASE_URL = (
    "https://generativelanguage.googleapis.com/v1beta"
)

DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"

OPEN_LIBRARY_BOOKS_URL = "https://openlibrary.org/api/books"
OPEN_LIBRARY_TIMEOUT = 30
MAX_COVER_BYTES = 5 * 1024 * 1024

class LibraryBook(models.Model):
    _name = "library.book"
    _description = "Library Book"
    _inherit = ["mail.thread"]
    _order = "name"


    # Campos básicos del libro
    name = fields.Char(
        string="Book Title",
        required=True,
        index=True,
    )

    isbn = fields.Char(
        string="ISBN",
    )

    openlibrary_key = fields.Char(
        string="Open Library ID",
        index=True,
        help="Open Library work ID (for example, OL123W) or edition ID "
             "(for example, OL123M).",
    )

    publication_year = fields.Integer(
        string="Publication Year",
    )

    pages = fields.Integer(
        string="Pages",
    )

    description = fields.Text(
        string="Description",
    )

    cover_image = fields.Image(
        string="Cover Image",
        max_width=1024,
        max_height=1024,
    )

    cover_image_128 = fields.Image(
        string="Cover Thumbnail",
        related="cover_image",
        max_width=128,
        max_height=128,
        store=True,
    )

    author_id = fields.Many2one(
        "library.author",
        string="Author",
        ondelete="restrict",
        index=True,
        tracking=True,
    )

    state = fields.Selection(
        [
            ("available", "Available"),
            ("borrowed", "Borrowed"),
            ("lost", "Lost"),
        ],
        string="Status",
        default="available",
        tracking=True,
    )

    category_ids = fields.Many2many(
        "library.category",
        "library_book_category_rel",
        "book_id",
        "category_id",
        string="Categories",
    )

    loan_ids = fields.One2many(
        "library.loan",
        "book_id",
        string="Loans",
    )

    loan_count = fields.Integer(
        string="Loan Count",
        compute="_compute_loan_count",
    )

    # Restricciones SQL para garantizar la unicidad y validez de los datos
    _sql_constraints = [
        (
            "isbn_unique",
            "UNIQUE(isbn)",
            "The ISBN must be unique.",
        ),
        (
            "name_author_unique",
            "UNIQUE(name, author_id)",
            "This author already has a book with that title.",
        ),
        (
            "pages_positive",
            "CHECK(pages >= 0)",
            "The number of pages cannot be negative.",
        ),
    ]

    # Campos calculados y dependientes de otros campos
    @api.depends("loan_ids")
    def _compute_loan_count(self):
        data = self.env["library.loan"]._read_group(
            [("book_id", "in", self.ids)], ["book_id"], ["__count"]
        )
        counts = {book.id: count for book, count in data}
        for book in self:
            book.loan_count = counts.get(book.id, 0)

    # Restricciones de validación para garantizar la coherencia de los datos
    @api.constrains("publication_year")
    def _check_publication_year(self):
        current_year = date.today().year

        for book in self:
            if book.publication_year and book.publication_year > current_year:
                raise ValidationError(
                    _(
                        "The publication year cannot be "
                        "later than %s."
                    ) % current_year
                )

    # Acciones para cambiar el estado del libro y gestionar préstamos
    def action_borrow(self):
        if any(
            book.state != "available"
            for book in self
        ):
            raise UserError(
                _("Only available books can be borrowed.")
            )

        self.write({"state": "borrowed"})

    def action_return(self):
        if any(
            book.state != "borrowed"
            for book in self
        ):
            raise UserError(
                _("Only borrowed books can be returned.")
            )

        self.write({"state": "available"})

    def action_mark_lost(self):
        if any(
            book.state == "lost"
            for book in self
        ):
            raise UserError(
                _("This book is already marked as lost.")
            )

        # El préstamo en curso de estos libros pasa a "perdido": queda
        # constancia de quién lo tenía y ya no se puede devolver.
        lost_loans = self.env["library.loan"].search([
            ("book_id", "in", self.ids),
            ("state", "=", "ongoing"),
        ])
        lost_loans.write({"state": "lost"})

        # El socio que lo tenía se suspende. No se reactiva al recuperar el
        # libro: puede haberse repuesto con otro ejemplar y eso no lo absuelve.
        for loan in lost_loans:
            loan._suspend_member(
                _("Suspended automatically: the book '%(book)s' was lost "
                  "during loan %(loan)s.") % {
                    "book": loan.book_id.name,
                    "loan": loan.name,
                })

        self.write({"state": "lost"})

    def action_recover(self):
        if any(
            book.state != "lost"
            for book in self
        ):
            raise UserError(
                _("Only lost books can be recovered.")
            )

        self.write({"state": "available"})

    # Acción para ver los préstamos asociados a un libro
    def action_view_loans(self):
        self.ensure_one()

        return {
            "name": _("Loans"),
            "type": "ir.actions.act_window",
            "res_model": "library.loan",
            "view_mode": "tree,form",
            "domain": [
                ("book_id", "=", self.id)
            ],
            "context": {
                "default_book_id": self.id
            },
        }

    # --- Autorrelleno por ISBN (Open Library) ----------------------------
    @api.model
    def _normalize_isbn(self, value):
        """Quita guiones y espacios y deja el ISBN en mayúsculas."""
        return "".join(
            char
            for char in (value or "").upper()
            if char not in " -"
        )

    @api.model
    def _normalize_openlibrary_book_key(self, value):
        value = (value or "").strip().upper()
        match = re.fullmatch(
            r"(?:HTTPS?://OPENLIBRARY\.ORG)?"
            r"(?:/(?:WORKS|BOOKS)/)?(OL\d+[WM])"
            r"(?:\.JSON)?(?:/[^?]*)?",
            value,
        )
        return match.group(1) if match else False

    @api.model
    def _is_valid_isbn(self, isbn):
        """Comprueba la longitud y el dígito de control (ISBN-10 o 13)."""
        if len(isbn) == 10:
            if not isbn[:9].isdigit() or not (
                isbn[9].isdigit() or isbn[9] == "X"
            ):
                return False
            total = sum(
                (10 - index)
                * (10 if char == "X" else int(char))
                for index, char in enumerate(isbn)
            )
            return total % 11 == 0

        if len(isbn) == 13:
            if not isbn.isdigit() or isbn[:3] not in ("978", "979"):
                return False
            total = sum(
                int(char) * (1 if index % 2 == 0 else 3)
                for index, char in enumerate(isbn)
            )
            return total % 10 == 0

        return False

    @api.model
    def _extract_publication_year(self, value):
        """Extrae un año válido de fechas como '1988' o 'March 1988'."""
        match = re.search(r"\b(\d{4})\b", value or "")
        if not match:
            return 0
        year = int(match.group(1))
        current_year = date.today().year
        return year if 1000 <= year <= current_year else 0

    def _check_isbn_access(self):
        """Solo los bibliotecarios pueden consultar la API externa."""
        if not self.env.su and not self.env.user.has_group(
            "library_manager.group_library_manager"
        ):
            raise AccessError(
                _("Only librarians can use the ISBN autofill.")
            )

    @api.model
    def _get_or_create_author(self, name, author_key=False, author_data=None):
        """Reconcile an Open Library author with local records before creating."""
        name = (name or "").strip()
        Author = self.env["library.author"]
        if not name and not author_key:
            return Author

        author_data = author_data or {}
        canonical_name = (author_data.get("name") or name).strip()
        alternate_names = author_data.get("alternate_names") or []
        if isinstance(alternate_names, str):
            alternate_names = [alternate_names]
        aliases = {
            Author._normalize_openlibrary_name(alias)
            for alias in [name, canonical_name, *alternate_names]
            if isinstance(alias, str) and alias.strip()
        }

        author = Author.search(
            [("openlibrary_key", "=", author_key)], limit=1
        ) if author_key else Author

        if not author and aliases:
            candidates = Author.search([])
            matching = candidates.filtered(
                lambda record: Author._normalize_openlibrary_name(record.name) in aliases
            )
            if len(matching) > 1:
                raise UserError(_(
                    "Several local authors match '%(name)s'. Resolve the "
                    "ambiguity by assigning the correct Open Library ID to "
                    "the author record, then retry ISBN autofill."
                ) % {"name": canonical_name or name})
            author = matching[:1]

        if not author:
            if not (canonical_name or name):
                return Author
            author = Author.create({"name": canonical_name or name})

        values = {}
        if canonical_name and author.name != canonical_name:
            name_collision = Author.search([
                ("name", "=ilike", canonical_name),
                ("id", "!=", author.id),
            ], limit=1)
            if name_collision:
                raise UserError(_(
                    "Open Library author '%s' conflicts with another local "
                    "author record. Resolve the duplicate before using ISBN autofill."
                ) % canonical_name)
            values["name"] = canonical_name
        if author_key and author.openlibrary_key != author_key:
            values["openlibrary_key"] = author_key

        birth_date = Author._openlibrary_birth_date(
            author_data.get("birth_date")
        )
        if birth_date:
            values["birth_date"] = birth_date
        bio = Author._openlibrary_bio(author_data.get("bio"))
        if bio:
            values["bio"] = bio
        if values:
            author.write(values)
        return author

    def _fetch_open_library_data(self, isbn):
        """Consulta Open Library y devuelve los datos del ISBN indicado."""
        try:
            if self.env.context.get("openlibrary_bulk_refresh"):
                time.sleep(1)
            _logger.info(
                "Requesting Open Library data for ISBN %s", isbn
            )
            response = requests.get(
                OPEN_LIBRARY_BOOKS_URL,
                params={
                    "bibkeys": f"ISBN:{isbn}",
                    "format": "json",
                    "jscmd": "data",
                },
                timeout=OPEN_LIBRARY_TIMEOUT,
            )

        except requests.exceptions.Timeout:
            raise UserError(
                _(
                    "Open Library did not respond within 30 seconds. "
                    "Please try again."
                )
            )

        except requests.exceptions.RequestException:
            _logger.exception(
                "Network error connecting to Open Library"
            )
            raise UserError(
                _(
                    "Could not connect to Open Library. "
                    "Check the server internet connection."
                )
            )

        if response.status_code == 404:
            raise UserError(
                _(
                    "Open Library has no data for ISBN %s. "
                    "Check the ISBN or try later."
                ) % isbn
            )

        if not response.ok:
            _logger.error(
                "Open Library error. Status: %s, ISBN: %s",
                response.status_code,
                isbn,
            )
            raise UserError(
                _("Open Library returned an error (HTTP %s).")
                % response.status_code
            )

        try:
            result = response.json()
        except ValueError:
            _logger.warning(
                "Invalid Open Library response for ISBN %s", isbn
            )
            raise UserError(
                _("Open Library returned an invalid response.")
            )

        data = (
            result.get(f"ISBN:{isbn}")
            if isinstance(result, dict)
            else None
        )

        if not data:
            raise UserError(
                _(
                    "Open Library has no data for ISBN %s. "
                    "Check the ISBN or try later."
                ) % isbn
            )

        return data

    def _fetch_open_library_record(self, route, key):
        """Fetch one work or edition by its Open Library ID."""
        url = f"https://openlibrary.org/{route}/{key}.json"
        try:
            if self.env.context.get("openlibrary_bulk_refresh"):
                time.sleep(1)
            response = requests.get(url, timeout=OPEN_LIBRARY_TIMEOUT)
        except requests.exceptions.Timeout:
            raise UserError(_(
                "Open Library did not respond within 30 seconds. Please try again."
            ))
        except requests.exceptions.RequestException:
            _logger.exception("Network error fetching Open Library ID %s", key)
            raise UserError(_(
                "Could not connect to Open Library. Check the server internet connection."
            ))

        if response.status_code == 404:
            raise UserError(_("Open Library has no data for ID %s.") % key)
        if not response.ok:
            raise UserError(_(
                "Open Library returned an error (HTTP %s)."
            ) % response.status_code)
        try:
            data = response.json()
        except ValueError:
            raise UserError(_("Open Library returned an invalid response."))
        if not isinstance(data, dict):
            raise UserError(_("Open Library returned an invalid response."))
        return data

    @api.model
    def _prepare_openlibrary_key_data(self, key):
        """Adapt a Work or Edition record to the shape used by autofill."""
        is_work = key.endswith("W")
        record = self._fetch_open_library_record(
            "works" if is_work else "books", key
        )
        authors = record.get("authors") or []

        # Editions may omit the author list but refer to their parent work.
        work_record = {}
        if not is_work and not authors:
            works = record.get("works") or []
            work_key = False
            if works and isinstance(works[0], dict):
                work_key = self._normalize_openlibrary_book_key(
                    works[0].get("key")
                )
            if work_key:
                try:
                    work_record = self._fetch_open_library_record(
                        "works", work_key
                    )
                    authors = work_record.get("authors") or []
                except UserError:
                    _logger.warning(
                        "Could not fetch parent work %s for edition %s",
                        work_key,
                        key,
                    )

        normalized_authors = []
        for item in authors:
            if not isinstance(item, dict):
                continue
            author_ref = item.get("author")
            if not isinstance(author_ref, dict):
                author_ref = item
            normalized_authors.append({
                "name": item.get("name") or author_ref.get("name") or "",
                "key": author_ref.get("key") or author_ref.get("url") or "",
            })

        def first_cover_id(cover_ids):
            if not isinstance(cover_ids, (list, tuple)):
                cover_ids = [cover_ids]
            return next((value for value in cover_ids
                         if str(value).isdigit() and int(value) > 0), False)

        cover_id = (
            first_cover_id(record.get("covers"))
            or first_cover_id(work_record.get("covers"))
        )
        cover = ({
            "medium": f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg",
        } if cover_id else {})

        description = record.get("description") or work_record.get("description")
        if isinstance(description, dict):
            description = description.get("value")

        return {
            "title": record.get("title") or work_record.get("title") or "",
            "authors": normalized_authors,
            "publish_date": (
                record.get("publish_date")
                or record.get("first_publish_date")
                or work_record.get("first_publish_date")
            ),
            "number_of_pages": record.get("number_of_pages"),
            "cover": cover,
            "description": description,
            "openlibrary_key": key,
            # ISBNs identify editions, so only take them from an edition record.
            "identifiers": record.get("identifiers") or {},
            "isbn_10": record.get("isbn_10") or [],
            "isbn_13": record.get("isbn_13") or [],
        }

    def _fetch_cover_image(self, url):
        """Descarga la portada y la devuelve en base64, o None si falla.

        Un fallo con la imagen no debe impedir rellenar el resto de datos.
        """
        if not url:
            return None

        try:
            if self.env.context.get("openlibrary_bulk_refresh"):
                time.sleep(1)
            response = requests.get(
                url, timeout=OPEN_LIBRARY_TIMEOUT
            )
        except requests.exceptions.RequestException:
            _logger.warning(
                "Could not download the cover image %s", url
            )
            return None

        if not response.ok:
            _logger.warning(
                "Cover download failed with HTTP %s: %s",
                response.status_code,
                url,
            )
            return None

        content = response.content or b""

        if not content or len(content) > MAX_COVER_BYTES:
            _logger.warning(
                "Cover image skipped (empty or larger than 5 MB): %s",
                url,
            )
            return None

        content_type = (response.headers or {}).get(
            "Content-Type", ""
        )
        if content_type and not content_type.startswith("image/"):
            _logger.warning(
                "Cover URL did not return an image: %s", url
            )
            return None

        return base64.b64encode(content).decode("ascii")

    def _prepare_isbn_values(self, data, isbn=False, openlibrary_key=False):
        """Prepare book values returned by Open Library for ISBN or OLID lookup."""
        values = {}
        isbn_conflict = False
        if isbn:
            values["isbn"] = isbn
        else:
            identifiers = data.get("identifiers") or {}
            if not isinstance(identifiers, dict):
                identifiers = {}
            isbn_candidates = []
            for field in ("isbn_13", "isbn_10"):
                for source in (data, identifiers):
                    candidates = source.get(field) or []
                    if isinstance(candidates, str):
                        isbn_candidates.append(candidates)
                    elif isinstance(candidates, (list, tuple)):
                        isbn_candidates.extend(candidates)
            for candidate in isbn_candidates:
                candidate = self._normalize_isbn(str(candidate or ""))
                if self._is_valid_isbn(candidate):
                    if not (
                        self.env.context.get("openlibrary_refresh_overwrite")
                        or not self.isbn
                    ):
                        break
                    else:
                        duplicate = self.search([
                            ("isbn", "=", candidate),
                            ("id", "!=", self._origin.id or 0),
                        ], limit=1)
                        if duplicate:
                            isbn_conflict = candidate
                            continue
                        values["isbn"] = candidate
                    break
        key = openlibrary_key or self._normalize_openlibrary_book_key(
            data.get("openlibrary_key") or data.get("url")
        )
        overwrite = self.env.context.get("openlibrary_refresh_overwrite")
        if key and (overwrite or openlibrary_key or not self.openlibrary_key):
            values["openlibrary_key"] = key

        title = (data.get("title") or "").strip()
        if title and (overwrite or not self.name):
            values["name"] = title

        if data.get("authors"):
            authors = data.get("authors") or []
            author_name = ""
            author_key = False
            Author = self.env["library.author"]
            if authors and isinstance(authors[0], dict):
                author_ref = authors[0]
                author_name = (author_ref.get("name") or "").strip()
                author_key = Author._openlibrary_author_key(
                    author_ref.get("url") or author_ref.get("key")
                )
            if author_name or author_key:
                author_data = (
                    Author._fetch_open_library_author(author_key)
                    if author_key else {}
                )
                author = self._get_or_create_author(
                    author_name, author_key, author_data
                )
                if author and (overwrite or not self.author_id):
                    values["author_id"] = author.id

        if data.get("publish_date") and (overwrite or not self.publication_year):
            year = self._extract_publication_year(
                data.get("publish_date")
            )
            if year:
                values["publication_year"] = year

        if data.get("number_of_pages") and (overwrite or not self.pages):
            try:
                pages = int(data.get("number_of_pages") or 0)
            except (TypeError, ValueError):
                pages = 0
            if pages > 0:
                values["pages"] = pages

        description = data.get("description")
        if (isinstance(description, str) and description.strip()
                and (overwrite or not self.description)):
            values["description"] = description.strip()

        cover_failed = False
        if data.get("cover") and (overwrite or not self.cover_image):
            cover = data.get("cover") or {}
            cover_url = (
                cover.get("medium")
                or cover.get("large")
                or cover.get("small")
            )
            cover_image = self._fetch_cover_image(cover_url)
            if cover_image:
                values["cover_image"] = cover_image
            elif cover_url:
                cover_failed = True

        return values, cover_failed, isbn_conflict

    def action_fill_from_isbn(self):
        """Rellena el libro desde Open Library por ISBN o por su ID.

        Completa los campos vacíos. Si el libro todavía no está guardado, se
        crea directamente para poder rellenar el título.
        """
        self.ensure_one()
        self._check_isbn_access()

        raw_key = (self.openlibrary_key or "").strip()
        if raw_key:
            openlibrary_key = self._normalize_openlibrary_book_key(raw_key)
            if not openlibrary_key:
                raise UserError(_(
                    "Open Library ID '%s' is invalid. Enter a work ID "
                    "(OL…W) or an edition ID (OL…M)."
                ) % raw_key)
            data = self._prepare_openlibrary_key_data(openlibrary_key)
            isbn = False
        else:
            raw_isbn = (self.isbn or "").strip()
            if not raw_isbn:
                raise UserError(_(
                    "Enter an ISBN or an Open Library ID first."
                ))

            isbn = self._normalize_isbn(raw_isbn)
            if not self._is_valid_isbn(isbn):
                raise UserError(
                    _(
                        "ISBN '%s' is not valid. "
                        "Check the number and its check digit."
                    ) % raw_isbn
                )

            duplicate_domain = [("isbn", "=", isbn)]
            if self._origin.id:
                duplicate_domain.append(("id", "!=", self._origin.id))
            duplicate = self.search(duplicate_domain, limit=1)
            if duplicate:
                raise UserError(
                    _(
                        "A book with ISBN %(isbn)s already exists: "
                        "%(title)s."
                    ) % {"isbn": isbn, "title": duplicate.name}
                )

            data = self._fetch_open_library_data(isbn)
            openlibrary_key = False

        values, cover_failed, isbn_conflict = self._prepare_isbn_values(
            data, isbn, openlibrary_key
        )

        # Libro nuevo: se guarda con lo obtenido y se reabre el formulario.
        if not self._origin.id:
            create_values = {
                "name": (self.name or "").strip(),
                "isbn": self.isbn or False,
                "openlibrary_key": self.openlibrary_key or False,
                "author_id": self.author_id.id or False,
                "publication_year": self.publication_year or False,
                "pages": self.pages or False,
                "description": self.description or False,
                "cover_image": self.cover_image or False,
            }
            if self.category_ids:
                create_values["category_ids"] = [
                    (6, 0, self.category_ids.ids)
                ]
            create_values.update(values)
            if not create_values.get("name"):
                raise UserError(_(
                    "Open Library did not return a title for this book identifier."
                ))
            book = self.create(create_values)
            return {
                "type": "ir.actions.act_window",
                "res_model": "library.book",
                "res_id": book.id,
                "view_mode": "form",
                "target": "current",
            }

        filled = []
        if "name" in values:
            filled.append(_("title"))
        if "author_id" in values:
            filled.append(_("author"))
        if "publication_year" in values:
            filled.append(_("publication year"))
        if "pages" in values:
            filled.append(_("pages"))
        if "cover_image" in values:
            filled.append(_("cover"))
        if "description" in values:
            filled.append(_("description"))
        if "openlibrary_key" in values:
            filled.append(_("Open Library ID"))
        if "isbn" in values and not isbn:
            filled.append(_("ISBN"))

        self.write(values)

        if filled:
            message = _(
                "Filled from Open Library: %s."
            ) % ", ".join(filled)
            notification_type = "success"
        else:
            message = _(
                "Open Library returned data, but the book "
                "fields were already filled."
            )
            notification_type = "warning"

        if cover_failed:
            message = _(
                "%(message)s The cover could not be downloaded."
            ) % {"message": message}
            notification_type = "warning"

        if isbn_conflict:
            message += " " + _(
                "ISBN %(isbn)s was not added because another book already uses it."
            ) % {"isbn": isbn_conflict}
            notification_type = "warning"

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Book Autofill"),
                "message": message,
                "type": notification_type,
                "sticky": False,
            },
        }

    def action_queue_openlibrary_refresh(self):
        self._check_isbn_access()
        if not self:
            raise UserError(_("Select at least one book to refresh."))

        eligible = self.filtered(lambda book: book.isbn or book.openlibrary_key)
        skipped = len(self) - len(eligible)
        if not eligible:
            raise UserError(_(
                "None of the selected books has an ISBN or Open Library ID."
            ))

        Queue = self.env["library.metadata.refresh"].sudo()
        existing_ids = set(Queue.search([
            ("state", "in", ["queued", "processing"]),
            ("book_id", "in", eligible.ids),
        ]).mapped("book_id").ids)
        to_queue = eligible.filtered(lambda book: book.id not in existing_ids)
        if to_queue:
            Queue.create([{"book_id": book.id} for book in to_queue])

        if not to_queue:
            message = _("The selected books already have queued refreshes.")
        else:
            message = _(
                "Queued %s book refreshes. Check Configuration > Open Library Refreshes for progress."
            ) % len(to_queue)
        if skipped:
            message += " " + _(
                "%s books were skipped because they have no ISBN or Open Library ID."
            ) % skipped
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Open Library Refresh"),
                "message": message,
                "type": "success" if to_queue else "warning",
                "sticky": False,
            },
        }

    # Acción para sugerir categorías usando la API de Gemini
    def action_suggest_categories(self):
        self.ensure_one()

        # Solo los bibliotecarios pueden gastar cuota de la API.
        if not self.env.su and not self.env.user.has_group(
            "library_manager.group_library_manager"
        ):
            raise AccessError(
                _("Only librarians can use the AI category suggestion.")
            )

        # Obtener configuración de Odoo
        params = self.env[
            "ir.config_parameter"
        ].sudo()

        api_key = params.get_param(
            "library_manager.gemini_api_key"
        )

        if not api_key or not api_key.strip():
            raise UserError(
                _(
                    "No Gemini API key configured.\n\n"
                    "Go to Settings > Library and set the "
                    "Gemini API Key."
                )
            )

        api_key = api_key.strip()

        model_name = (
            params.get_param(
                "library_manager.gemini_model",
                DEFAULT_GEMINI_MODEL,
            )
            or DEFAULT_GEMINI_MODEL
        ).strip()

        # Evitar modelos con rutas arbitrarias
        if not model_name.startswith("gemini-") or not all(
            char.isalnum() or char in "-_."
            for char in model_name
        ):
            raise UserError(
                _("Invalid Gemini model configuration.")
            )

        # Buscar categorías existentes
        categories = self.env[
            "library.category"
        ].search([])

        if not categories:
            raise UserError(
                _(
                    "There are no categories to choose from. "
                    "Create categories first."
                )
            )

        # Preparar información del libro
        category_names = categories.mapped("name")

        author_name = (
            self.author_id.name
            if self.author_id
            else "Unknown"
        )

        description = (
            self.description or "No description"
        )

        # Construir prompt
        prompt = (
            "You are a professional librarian "
            "specialized in book classification.\n\n"

            "Analyze the following book and choose "
            "up to 3 appropriate categories.\n\n"

            "IMPORTANT RULES:\n"
            "1. Use ONLY categories from the "
            "available categories list.\n"
            "2. Do not invent new categories.\n"
            "3. Return a JSON array of strings.\n"
            "4. Return a maximum of 3 categories.\n"
            "5. Do not include explanations.\n\n"

            "AVAILABLE CATEGORIES:\n"
            f"{json.dumps(category_names, ensure_ascii=False)}\n\n"

            "BOOK INFORMATION:\n"
            f"Title: {self.name}\n"
            f"Author: {author_name}\n"
            f"Publication year: {self.publication_year or 'Unknown'}\n"
            f"Description: {description}\n\n"

            "Example response:\n"
            '["Fantasy", "Adventure"]'
        )

        # URL oficial de Gemini
        url = (
            f"{GEMINI_BASE_URL}/models/"
            f"{model_name}:generateContent"
        )

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        }

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": prompt
                        }
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
                "maxOutputTokens": 1024,
            },
        }

        # Llamada a la API de Gemini con manejo de errores y registro
        try:
            _logger.info(
                "Requesting Gemini category suggestions "
                "for book ID %s using model %s",
                self.id,
                model_name,
            )

            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=30,
            )

        except requests.exceptions.Timeout:
            raise UserError(
                _(
                    "Gemini did not respond within 30 seconds. "
                    "Please try again."
                )
            )

        except requests.exceptions.RequestException:
            _logger.exception(
                "Network error connecting to Gemini"
            )
            raise UserError(
                _(
                    "Could not connect to Gemini. "
                    "Check the server internet connection."
                )
            )

        # Manejo de errores HTTP y registro de respuestas de Gemini
        if not response.ok:
            try:
                error_data = response.json()
                error_info = error_data.get("error", {})
                error_message = error_info.get(
                    "message",
                    "Unknown API error",
                )
            except (ValueError, AttributeError):
                error_message = "Unknown API error"

            _logger.error(
                "Gemini API error. Status: %s, "
                "Model: %s, Message: %s",
                response.status_code,
                model_name,
                error_message,
            )

            if response.status_code == 400:
                raise UserError(
                    _(
                        "Gemini rejected the request.\n\n%s"
                    ) % error_message
                )

            if response.status_code in (401, 403):
                raise UserError(
                    _(
                        "Gemini API authentication or "
                        "permission error.\n\n"
                        "Check your API key and "
                        "project permissions.\n\n%s"
                    ) % error_message
                )

            if response.status_code == 404:
                raise UserError(
                    _(
                        "Gemini model '%s' was not found "
                        "or is not available for your API key.\n\n"
                        "Configure a supported model in:\n"
                        "library_manager.gemini_model\n\n"
                        "Google response: %s"
                    ) % (model_name, error_message)
                )

            if response.status_code == 429:
                raise UserError(
                    _(
                        "Gemini API quota or rate limit "
                        "exceeded.\n\n%s"
                    ) % error_message
                )

            raise UserError(
                _(
                    "Gemini API error (HTTP %s):\n%s"
                ) % (
                    response.status_code,
                    error_message,
                )
            )

        # Procesar la respuesta de Gemini y extraer categorías sugeridas
        try:
            result = response.json()

            candidates = result.get(
                "candidates", []
            )

            if not candidates:
                raise ValueError(
                    "Gemini returned no candidates."
                )

            parts = candidates[0].get(
                "content", {}
            ).get("parts", [])

            text = "".join(
                part.get("text", "")
                for part in parts
            ).strip()

            if not text:
                raise ValueError(
                    "Gemini returned an empty response."
                )

            # Eliminar posibles bloques Markdown
            if text.startswith("```"):
                lines = text.splitlines()

                if lines and lines[0].startswith("```"):
                    lines = lines[1:]

                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]

                text = "\n".join(lines).strip()

            names = json.loads(text)

            if not isinstance(names, list):
                raise ValueError(
                    "Gemini response is not a JSON array."
                )

            if not all(
                isinstance(name, str)
                for name in names
            ):
                raise ValueError(
                    "Gemini returned invalid category names."
                )

        except (ValueError, KeyError, TypeError, IndexError) as err:
            _logger.warning(
                "Invalid Gemini response for book %s: %s",
                self.id,
                str(err),
            )

            raise UserError(
                _(
                    "Gemini returned an invalid category "
                    "response.\n\nDetails: %s"
                ) % str(err)
            )

        # Filtrar categorías sugeridas que coincidan con las existentes y añadirlas al libro
        wanted = {
            name.strip().casefold()
            for name in names[:3]
            if name.strip()
        }

        matched = categories.filtered(
            lambda category: (
                category.name or ""
            ).strip().casefold() in wanted
        )

        # Máximo 3 categorías
        matched = matched[:3]

        # Añadir sin eliminar categorías anteriores
        if matched:
            self.write({
                "category_ids": [
                    (4, category.id)
                    for category in matched
                ]
            })

            message = _(
                "Categories added: %s"
            ) % ", ".join(
                matched.mapped("name")
            )

            notification_type = "success"

        else:
            message = _(
                "Gemini did not suggest any matching "
                "categories."
            )

            notification_type = "warning"

        _logger.info(
            "Gemini classification completed for "
            "book ID %s. Categories: %s",
            self.id,
            matched.mapped("name"),
        )

        # Devolver notificación al usuario con el resultado de la acción
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("AI Category Suggestion"),
                "message": message,
                "type": notification_type,
                "sticky": False,
            },
        }
