from odoo import models, fields

class LibraryBook(models.Model):
    _name = 'library.book'
    _description = 'Library Book'
    _order = 'name'

    name = fields.Char(string='Book Title', required=True, index=True)
    isbn = fields.Char(string='ISBN')
    pages = fields.Integer(string='Pages')
    description = fields.Text(string='Description')
    
    # Many2one relacion con el autor
    author_id = fields.Many2one(
        'library.author', 
        string='Author', 
        ondelete='cascade', 
        index=True
    )
    
    state = fields.Selection([
        ('available', 'Available'),
        ('borrowed', 'Borrowed'),
        ('lost', 'Lost'),
    ], string='Status', default='available', tracking=True)