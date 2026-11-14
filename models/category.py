from odoo import models, fields

class LibraryCategory(models.Model):
    _name = 'library.category'
    _description = 'Library Category'

    name = fields.Char(string='Category Name', required=True)
    description = fields.Text(string='Description')

    book_ids = fields.Many2many(
        'library.book', 
        'library_book_category_rel', 
        'category_id', 
        'book_id', 
        string='Books')
