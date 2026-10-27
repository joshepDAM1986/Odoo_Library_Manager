from odoo import fields, models, api, _
from odoo.exceptions import ValidationError, UserError

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
    
    member_state = fields.Selection(related='member_id.state', string='Member Status')

    @api.constrains('loan_date', 'due_date', 'return_date')
    def _check_dates(self):
        for loan in self:
            if loan.due_date < loan.loan_date:
                raise ValidationError(_("The due date cannot be earlier than the loan date."))
            if loan.return_date and loan.return_date < loan.loan_date:
                raise ValidationError(_("The return date cannot be earlier than the loan date."))

    def action_confirm(self):
        for loan in self:
            if loan.state != 'draft':
                raise UserError(_("Only draft loans can be confirmed."))
            if loan.member_id.state != 'active':
                raise UserError(_("The member must be active to confirm the loan."))
            loan.book_id.action_borrow()
            loan.state = 'ongoing'

    def action_return(self):
        for loan in self:
            if loan.state != 'ongoing':
                raise UserError(_("Only ongoing loans can be returned."))
            loan.book_id.action_return()
            loan.write({'return_date': fields.Date.context_today(self), 'state': 'returned'})

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
              vals['name'] = self.env['ir.sequence'].next_by_code('library.loan')
        return super().create(vals_list)

    @api.ondelete(at_uninstall=False)
    def _unlink_only_draft(self):
        for loan in self:
            if loan.state != 'draft':
                raise UserError(_("Only draft loans can be deleted. Return or cancel the loan instead."))
                
            
                