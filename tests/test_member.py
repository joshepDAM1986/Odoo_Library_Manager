from odoo import fields
from odoo.tests.common import TransactionCase


class TestMember(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Member = cls.env['library.member']

    def test_member_number_is_generated(self):
        member = self.Member.create({'name': 'Ana Test'})
        self.assertTrue(member.member_number.startswith('LM'))

    def test_member_numbers_are_different(self):
        first = self.Member.create({'name': 'Member One'})
        second = self.Member.create({'name': 'Member Two'})
        self.assertNotEqual(first.member_number, second.member_number)

    def test_partner_is_created(self):
        member = self.Member.create({'name': 'Ana Test', 'email': 'ana@example.com'})
        self.assertTrue(member.partner_id)
        self.assertEqual(member.partner_id.name, 'Ana Test')
        self.assertEqual(member.partner_id.email, 'ana@example.com')

    def test_default_values(self):
        member = self.Member.create({'name': 'Ana Test'})
        self.assertEqual(member.state, 'active')
        self.assertEqual(member.join_date, fields.Date.context_today(member))

    def test_suspend_and_activate(self):
        member = self.Member.create({'name': 'Ana Test'})
        member.action_suspend()
        self.assertEqual(member.state, 'suspended')
        member.action_activate()
        self.assertEqual(member.state, 'active')

    def test_suspended_member_is_marked_in_display_name(self):
        member = self.Member.create({'name': 'Ana Test'})
        self.assertEqual(member.display_name, 'Ana Test')
        member.action_suspend()
        self.assertIn('(Suspended)', member.display_name)
