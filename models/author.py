from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LibraryAuthor(models.Model):
    _name = 'library.author'
    _description = 'Library Author'
    _order = 'name'

    name = fields.Char(string='Author Name', required=True, index=True)
    birth_date = fields.Date(string='Birth Date')
    bio = fields.Text(string='Biography')

    # One2many relacion con los libros
    book_ids = fields.One2many(
        'library.book',
        'author_id',
        string='Books',
    )

    # Contador dinamico de libros de cada autor
    book_count = fields.Integer(string='Book Count', compute='_compute_book_count')

    total_pages = fields.Integer(
        string='Total Pages Written',
        compute='_compute_total_pages',
        store=True,
    )

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'The author name must be unique.'),
    ]

    @api.depends('book_ids')
    def _compute_book_count(self):
        for author in self:
            author.book_count = len(author.book_ids)

    @api.depends('book_ids.pages')
    def _compute_total_pages(self):
        for author in self:
            author.total_pages = sum(author.book_ids.mapped('pages'))

    def action_view_author_books(self):
        self.ensure_one()
        return {
            'name': _('Books'),
            'type': 'ir.actions.act_window',
            'res_model': 'library.book',
            'view_mode': 'tree,form',
            'domain': [('author_id', '=', self.id)],
            'context': {'default_author_id': self.id},
        }

    @api.constrains('birth_date')
    def _check_birth_date(self):
        today = fields.Date.today()
        for author in self:
            if author.birth_date and author.birth_date > today:
                raise ValidationError(_("The birth date cannot be in the future!"))
