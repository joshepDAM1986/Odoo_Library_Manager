import json
import logging
from datetime import date

import requests

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

ANTHROPIC_URL = 'https://api.anthropic.com/v1/messages'
DEFAULT_AI_MODEL = 'claude-haiku-5-5'


class LibraryBook(models.Model):
    _name = 'library.book'
    _description = 'Library Book'
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char(string='Book Title', required=True, index=True)
    isbn = fields.Char(string='ISBN')
    publication_year = fields.Integer(string='Publication Year')
    pages = fields.Integer(string='Pages')
    description = fields.Text(string='Description')

    # Many2one relacion con el autor.
    # 'restrict': no se puede borrar un autor que todavia tiene libros.
    author_id = fields.Many2one(
        'library.author',
        string='Author',
        ondelete='restrict',
        index=True,
        tracking=True,
    )

    state = fields.Selection([
        ('available', 'Available'),
        ('borrowed', 'Borrowed'),
        ('lost', 'Lost'),
    ], string='Status', default='available', tracking=True)

    category_ids = fields.Many2many(
        'library.category',
        'library_book_category_rel',
        'book_id',
        'category_id',
        string='Categories',
    )

    loan_ids = fields.One2many('library.loan', 'book_id', string='Loans')
    loan_count = fields.Integer(string='Loan Count', compute='_compute_loan_count')

    _sql_constraints = [
        ('isbn_unique', 'UNIQUE(isbn)', 'The ISBN must be unique.'),
        ('name_author_unique', 'UNIQUE(name, author_id)',
         'This author already has a book with that title.'),
        ('pages_positive', 'CHECK(pages >= 0)', 'The number of pages cannot be negative.'),
    ]

    @api.depends('loan_ids')
    def _compute_loan_count(self):
        for book in self:
            book.loan_count = len(book.loan_ids)

    @api.constrains('publication_year')
    def _check_publication_year(self):
        current_year = date.today().year
        for book in self:
            # 0 significa "sin informar"
            if book.publication_year and not (1000 <= book.publication_year <= current_year):
                raise ValidationError(_(
                    "The publication year must be between 1000 and %s.", current_year))

    # ------------------------------------------------------------------
    # Acciones de estado
    # Borrow / Return los usan los prestamos (library.loan); en la vista
    # del libro ya no hay botones para ellos.
    # ------------------------------------------------------------------
    def action_borrow(self):
        """Available -> Borrowed"""
        if any(book.state != 'available' for book in self):
            raise UserError(_("Only available books can be borrowed."))
        self.write({'state': 'borrowed'})

    def action_return(self):
        """Borrowed -> Available"""
        if any(book.state != 'borrowed' for book in self):
            raise UserError(_("Only borrowed books can be returned."))
        self.write({'state': 'available'})

    def action_mark_lost(self):
        """Available / Borrowed -> Lost"""
        if any(book.state == 'lost' for book in self):
            raise UserError(_("This book is already marked as lost."))
        self.write({'state': 'lost'})

    def action_recover(self):
        """Lost -> Available (el libro ha aparecido)"""
        if any(book.state != 'lost' for book in self):
            raise UserError(_("Only lost books can be recovered."))
        self.write({'state': 'available'})

    def action_view_loans(self):
        self.ensure_one()
        return {
            'name': _('Loans'),
            'type': 'ir.actions.act_window',
            'res_model': 'library.loan',
            'view_mode': 'tree,form',
            'domain': [('book_id', '=', self.id)],
            'context': {'default_book_id': self.id},
        }

    # ------------------------------------------------------------------
    # IA: sugerir categorias
    # ------------------------------------------------------------------
    def action_suggest_categories(self):
        """Pide a un LLM (API de Anthropic) que elija categorias EXISTENTES.

        Se envian a la API externa solo el titulo, el autor y la descripcion.
        La clave se guarda en un parametro del sistema, nunca en el codigo:
        Ajustes > Tecnico > Parametros del sistema >
        'library_manager.anthropic_api_key'. Opcional: 'library_manager.ai_model'.
        """
        self.ensure_one()
        params = self.env['ir.config_parameter'].sudo()
        api_key = params.get_param('library_manager.anthropic_api_key')
        if not api_key:
            raise UserError(_(
                "Set the system parameter 'library_manager.anthropic_api_key' "
                "(Settings > Technical > System Parameters) to use this feature."))

        categories = self.env['library.category'].search([])
        if not categories:
            raise UserError(_("There are no categories to choose from."))

        model = params.get_param('library_manager.ai_model') or DEFAULT_AI_MODEL
        prompt = (
            "You classify books. Choose up to 3 categories for the book below, "
            "using ONLY names from the list of available categories.\n"
            "Reply with a JSON array of category names and nothing else.\n\n"
            "Available categories: %s\n\n"
            "Book title: %s\nAuthor: %s\nDescription: %s"
        ) % (
            json.dumps(categories.mapped('name'), ensure_ascii=False),
            self.name,
            self.author_id.name or 'unknown',
            self.description or 'no description',
        )

        try:
            response = requests.post(
                ANTHROPIC_URL,
                headers={
                    'x-api-key': api_key,
                    'anthropic-version': '2023-06-01',
                    'content-type': 'application/json',
                },
                json={
                    'model': model,
                    'max_tokens': 200,
                    'messages': [{'role': 'user', 'content': prompt}],
                },
                timeout=30,
            )
            response.raise_for_status()
            text = response.json()['content'][0]['text']
            start, end = text.find('['), text.rfind(']')
            names = json.loads(text[start:end + 1])
            if not isinstance(names, list):
                raise ValueError("The answer is not a list")
        except (requests.RequestException, KeyError, IndexError, ValueError) as err:
            _logger.warning("Category suggestion failed for book %s: %s", self.id, err)
            raise UserError(_(
                "The AI service did not return a usable answer. Try again later.")) from err

        wanted = {name.strip().lower() for name in names if isinstance(name, str)}
        matched = categories.filtered(lambda c: c.name.strip().lower() in wanted)
        if matched:
            self.write({'category_ids': [(4, category.id) for category in matched]})
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Category suggestion"),
                'message': (_("Added: %s", ', '.join(matched.mapped('name')))
                            if matched else _("No matching category found.")),
                'type': 'success' if matched else 'warning',
                'sticky': False,
            },
        }
