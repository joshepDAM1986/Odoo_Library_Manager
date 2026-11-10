from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestPartnerInheritance(TransactionCase):

    def test_partner_sees_its_memberships(self):
        member = self.env['library.member'].create({'name': 'Partner Test'})
        partner = member.partner_id
        self.assertEqual(partner.member_ids, member)
        self.assertEqual(partner.library_member_count, 1)

    def test_partner_without_membership(self):
        partner = self.env['res.partner'].create({'name': 'Not a member'})
        self.assertEqual(partner.library_member_count, 0)

    def test_action_opens_the_memberships(self):
        member = self.env['library.member'].create({'name': 'Partner Test'})
        action = member.partner_id.action_view_library_member()
        self.assertEqual(action['res_model'], 'library.member')
        self.assertEqual(action['domain'], [('partner_id', '=', member.partner_id.id)])

    def test_create_member_from_existing_partner(self):
        partner = self.env['res.partner'].create({'name': 'Existing Contact'})
        partner.action_create_library_member()
        self.assertEqual(partner.library_member_count, 1)
        # Se reutiliza el contacto: no se duplica
        self.assertEqual(
            self.env['res.partner'].search_count([('name', '=', 'Existing Contact')]), 1)

    def test_create_member_skips_existing_members(self):
        member = self.env['library.member'].create({'name': 'Already Member'})
        with self.assertRaises(UserError):
            member.partner_id.action_create_library_member()
        self.assertEqual(member.partner_id.library_member_count, 1)

    def test_member_counters_are_per_record(self):
        # Los contadores usan _read_group: comprobamos que no se mezclan
        member_a = self.env['library.member'].create({'name': 'Counter A'})
        member_b = self.env['library.member'].create({'name': 'Counter B'})
        partners = member_a.partner_id | member_b.partner_id
        self.assertEqual(partners.mapped('library_member_count'), [1, 1])
