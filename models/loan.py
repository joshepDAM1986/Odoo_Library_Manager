from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

class Loan(models.Model):
    _name = 'library.loan'
    _description = 'Loan'
    _inherit = ['mail.thread']
    _order = 'loan_date desc, id desc'

    name = fields.Char(string='Loan reference', required=True, readonly=True,
                   copy=False, default='New')
    
    book_id = fields.Many2one('library.book', string='Book', required=True, 
                              ondelete='restrict', tracking=True, domain=[('state', '=', 'available')])
    
    member_id = fields.Many2one('library.member', string='Member', required=True, 
                                ondelete='restrict', tracking=True)
    
    loan_date = fields.Date(string='Loan Date', required=True,
                        default=fields.Date.context_today)
    
    due_date = fields.Date(string='Due Date', required=True)

    return_date = fields.Date(string='Return Date', readonly=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('ongoing', 'Ongoing'),
        ('returned', 'Returned')], string='Status', default='draft', tracking=True)

    @api.constrains('loan_date', 'due_date', 'return_date')
    def _check_dates(self):
        for loan in self:
            if loan.due_date < loan.loan_date:
                raise ValidationError(_("The due date cannot be earlier than the loan date."))
            
                