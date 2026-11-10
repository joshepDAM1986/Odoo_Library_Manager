from odoo import _, api, fields, models
from odoo.exceptions import UserError


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
        data = self.env['library.member']._read_group(
            [('partner_id', 'in', self.ids)], ['partner_id'], ['__count'])
        counts = {partner.id: count for partner, count in data}
        for partner in self:
            partner.library_member_count = counts.get(partner.id, 0)

    def action_view_library_member(self):
        self.ensure_one()
        return {
            'name': _('Library Memberships'),
            'type': 'ir.actions.act_window',
            'res_model': 'library.member',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.id)],
        }

    def action_create_library_member(self):
        """Convierte contactos existentes en socios (sin duplicar el contacto)."""
        Member = self.env['library.member']
        existing = Member.with_context(active_test=False).search(
            [('partner_id', 'in', self.ids)]).mapped('partner_id')
        members = Member.create(
            [{'partner_id': partner.id} for partner in self - existing])
        if not members:
            raise UserError(
                _("The selected contacts are already library members."))
        action = {
            'name': _('Library Members'),
            'type': 'ir.actions.act_window',
            'res_model': 'library.member',
            'domain': [('id', 'in', members.ids)],
        }
        if len(members) == 1:
            action.update(view_mode='form', res_id=members.id)
        else:
            action.update(view_mode='tree,form')
        return action
