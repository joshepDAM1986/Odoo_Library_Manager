from odoo.addons.library_manager.models.name_initial import name_initial
from odoo.tests.common import TransactionCase


class TestNameInitial(TransactionCase):

    def test_helper_ignores_accents_case_and_leading_punctuation(self):
        self.assertEqual(name_initial('Agatha Christie'), 'A')
        self.assertEqual(name_initial('\u00c9dgar Neville'), 'E')
        self.assertEqual(name_initial('  \u00abAn\u00f3nimo\u00bb'), 'A')
        self.assertEqual(name_initial('\u0142ukasz'), 'L')

    def test_helper_groups_non_latin_and_numbers_under_hash(self):
        for name in ('1984 Press', '\u0414\u043e\u0441\u0442\u043e\u0435\u0432\u0441\u043a\u0438\u0439', '', False, '---'):
            self.assertEqual(name_initial(name), '#', name)

    def test_helper_never_returns_two_characters(self):
        # 'ss'.upper() == 'SS': no debe producir un valor fuera de la selección
        self.assertEqual(name_initial('\u00df'), 'S')

    def test_author_initial_is_computed_and_follows_the_name(self):
        author = self.env['library.author'].create({'name': '\u00c9dgar Allan Poe'})
        self.assertEqual(author.name_initial, 'E')
        author.name = 'Zane Grey'
        self.assertEqual(author.name_initial, 'Z')

    def test_member_initial_follows_the_linked_contact_name(self):
        member = self.env['library.member'].create({'name': 'Ana Test'})
        self.assertEqual(member.name_initial, 'A')
        member.partner_id.name = 'Bea Test'
        self.assertEqual(member.name_initial, 'B')
