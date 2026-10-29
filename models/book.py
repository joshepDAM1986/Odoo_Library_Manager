
import json
import logging
from datetime import date

import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


_logger = logging.getLogger(__name__)

GEMINI_BASE_URL = (
    "https://generativelanguage.googleapis.com/v1beta"
)

# Modelo predeterminado para proyectos nuevos.
# Se puede cambiar desde los parámetros de Odoo.
DEFAULT_GEMINI_MODEL = "gemini-3.5-flash-lite"


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
        for book in self:
            book.loan_count = len(book.loan_ids)

    # Restricciones de validación para garantizar la coherencia de los datos
    @api.constrains("publication_year")
    def _check_publication_year(self):
        current_year = date.today().year

        for book in self:
            if book.publication_year and not (
                1000 <= book.publication_year <= current_year
            ):
                raise ValidationError(
                    _(
                        "The publication year must be "
                        "between 1000 and %s."
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

    # Acción para sugerir categorías usando la API de Gemini
    def action_suggest_categories(self):
        self.ensure_one()

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
                    "Go to Settings > Technical > "
                    "System Parameters and create:\n\n"
                    "library_manager.gemini_api_key"
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
