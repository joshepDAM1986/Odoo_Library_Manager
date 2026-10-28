from odoo import _, api, fields, models


class ResPartner(models.Model):
    # Sin _name: se AÑADEN campos y metodos al modelo existente res.partner
    _inherit = 'res.partner'

    # groups: los usuarios sin permisos de biblioteca ni ven estos campos
    # ni provocan errores de acceso al abrir un contacto.
    member_ids = fields.One2many(
        'library.member', 'partner_id',
        string='Library Memberships',
        groups='library_manager.group_library_user')
    library_member_count = fields.Integer(
        string='Library Memberships Count',
        compute='_compute_library_member_count',
        groups='library_manager.group_library_user')

    @api.depends('member_ids')
    def _compute_library_member_count(self):
        for partner in self:
            partner.library_member_count = len(partner.member_ids)

    def action_view_library_member(self):
        self.ensure_one()
        return {
            'name': _('Library Memberships'),
            'type': 'ir.actions.act_window',
            'res_model': 'library.member',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.id)],
        }
