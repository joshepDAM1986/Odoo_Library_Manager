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
