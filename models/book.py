from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


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

    _sql_constraints = [
        ('isbn_unique', 'UNIQUE(isbn)', 'The ISBN must be unique.'),
        ('name_author_unique', 'UNIQUE(name, author_id)',
         'This author already has a book with that title.'),
        ('pages_positive', 'CHECK(pages >= 0)', 'The number of pages cannot be negative.'),
    ]

    @api.constrains('publication_year')
    def _check_publication_year(self):
        current_year = date.today().year
        for book in self:
            # 0 significa "sin informar"
            if book.publication_year and not (1000 <= book.publication_year <= current_year):
                raise ValidationError(_(
                    "The publication year must be between 1000 and %s.", current_year))

    # Acciones de los botones de estado
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
