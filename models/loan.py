from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class LibraryLoan(models.Model):
    _name = 'library.loan'
    _description = 'Library Loan'
    _inherit = ['mail.thread']
    _order = 'loan_date desc, id desc'

    name = fields.Char(
        string='Loan Reference', required=True, readonly=True,
        copy=False, default='New')

    book_id = fields.Many2one(
        'library.book', string='Book', required=True,
        ondelete='restrict', tracking=True,
        domain=[('state', '=', 'available')])

    member_id = fields.Many2one(
        'library.member', string='Member', required=True,
        ondelete='restrict', tracking=True)

    loan_date = fields.Date(
        string='Loan Date', required=True,
        default=fields.Date.context_today)

    due_date = fields.Date(
        string='Due Date', required=True,
        default=lambda self: fields.Date.context_today(self) + timedelta(days=14))

    return_date = fields.Date(string='Return Date', readonly=True, tracking=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('ongoing', 'Ongoing'),
        ('returned', 'Returned'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    # Estado del socio, para poder avisar en el formulario
    member_state = fields.Selection(related='member_id.state', string='Member Status')

    # Dias de retraso: se calcula, no se guarda (depende de "hoy")
    days_overdue = fields.Integer(string='Days Overdue', compute='_compute_days_overdue')

    @api.depends('due_date', 'return_date', 'state')
    def _compute_days_overdue(self):
        today = fields.Date.context_today(self)
        for loan in self:
            loan.days_overdue = 0
            if not loan.due_date:
                continue
            if loan.state == 'ongoing':
                end_date = today
            elif loan.state == 'returned' and loan.return_date:
                end_date = loan.return_date
            else:
                continue
            loan.days_overdue = max((end_date - loan.due_date).days, 0)

    @api.constrains('loan_date', 'due_date', 'return_date')
    def _check_dates(self):
        for loan in self:
            if loan.due_date < loan.loan_date:
                raise ValidationError(_("The due date cannot be earlier than the loan date."))
            if loan.return_date and loan.return_date < loan.loan_date:
                raise ValidationError(_("The return date cannot be earlier than the loan date."))

    @api.ondelete(at_uninstall=False)
    def _unlink_only_draft(self):
        for loan in self:
            if loan.state != 'draft':
                raise UserError(_(
                    "Only draft loans can be deleted. Return or cancel the loan instead."))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('library.loan')
        return super().create(vals_list)

    # Flujo: draft -> ongoing -> returned  (o cancelled)
    def action_confirm(self):
        for loan in self:
            if loan.state != 'draft':
                raise UserError(_("Only draft loans can be confirmed."))
            if loan.member_id.state != 'active':
                raise UserError(_("The member must be active to confirm the loan."))
            # Reutilizamos la accion del libro: ya valida que este disponible
            loan.book_id.action_borrow()
            loan.state = 'ongoing'

    def action_return(self):
        for loan in self:
            if loan.state != 'ongoing':
                raise UserError(_("Only ongoing loans can be returned."))
            loan.book_id.action_return()
            loan.write({
                'state': 'returned',
                'return_date': fields.Date.context_today(self),
            })

    def action_cancel(self):
        for loan in self:
            if loan.state not in ('draft', 'ongoing'):
                raise UserError(_("Only draft or ongoing loans can be cancelled."))
            # Si estaba en curso, el libro vuelve a estar disponible
            if loan.state == 'ongoing' and loan.book_id.state == 'borrowed':
                loan.book_id.action_return()
            loan.state = 'cancelled'
