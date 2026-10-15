from odoo import models, fields, api

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
        string='Books'
    )

    # Contador dinamico de libros de cada autor
    book_count = fields.Interget(strings='Book Count', compute='_compute_book_count')

    @api.depends('book_ids')
    def _compute_book_count(self):
        for author in self:
            author.book_count = len(author.book.ids)