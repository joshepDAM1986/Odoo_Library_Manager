from odoo import api, fields, models


class LibraryMember(models.Model):
    _name = 'library.member'
    _description = 'Library Member'
    # _inherits = herencia por delegacion: cada socio tiene un res.partner
    # asociado y los campos del partner (name, email, phone...) se pueden
    # usar directamente en el socio, aunque se guardan en la tabla res_partner.
    _inherits = {'res.partner': 'partner_id'}
    _inherit = ['mail.thread']
    _order = 'member_number desc'

    partner_id = fields.Many2one(
        'res.partner',
        string='Contact',
        required=True,
        ondelete='restrict',
        index=True,
    )
    member_number = fields.Char(
        string='Member Number',
        readonly=True,
        copy=False,
        index=True,
    )
    join_date = fields.Date(
        string='Join Date',
        default=fields.Date.context_today,
    )
    state = fields.Selection([
        ('active', 'Active'),
        ('suspended', 'Suspended'),
    ], string='Status', default='active', tracking=True)
    notes = fields.Text(string='Notes')
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('member_number_unique', 'UNIQUE(member_number)',
         'The member number must be unique.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('member_number'):
                vals['member_number'] = self.env['ir.sequence'].next_by_code('library.member')
        return super().create(vals_list)

    def action_suspend(self):
        self.write({'state': 'suspended'})

    def action_activate(self):
        self.write({'state': 'active'})
