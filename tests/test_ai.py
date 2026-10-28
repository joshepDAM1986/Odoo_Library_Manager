from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

POST = 'odoo.addons.library_manager.models.book.requests.post'


def fake_response(text):
    response = MagicMock()
    response.json.return_value = {'content': [{'type': 'text', 'text': text}]}
    return response


class TestSuggestCategories(TransactionCase):
    """La API externa se simula con mock: los tests no hacen llamadas reales."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fiction = cls.env['library.category'].create({'name': 'Test Fiction'})
        cls.history = cls.env['library.category'].create({'name': 'Test History'})
        cls.book = cls.env['library.book'].create({
            'name': 'AI test book', 'description': 'A made-up story.'})

    def _set_key(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'library_manager.anthropic_api_key', 'test-key')

    def test_requires_api_key(self):
        self.env['ir.config_parameter'].sudo().set_param(
            'library_manager.anthropic_api_key', '')
        with self.assertRaises(UserError):
            self.book.action_suggest_categories()

    def test_adds_suggested_categories(self):
        self._set_key()
        with patch(POST, return_value=fake_response('["Test Fiction"]')):
            self.book.action_suggest_categories()
        self.assertEqual(self.book.category_ids, self.fiction)

    def test_ignores_unknown_categories(self):
        self._set_key()
        with patch(POST, return_value=fake_response('["Test History", "Does not exist"]')):
            self.book.action_suggest_categories()
        self.assertEqual(self.book.category_ids, self.history)

    def test_answer_wrapped_in_text_is_parsed(self):
        self._set_key()
        with patch(POST, return_value=fake_response('Sure! ["Test Fiction"] Hope it helps.')):
            self.book.action_suggest_categories()
        self.assertEqual(self.book.category_ids, self.fiction)

    def test_unusable_answer_raises_a_clear_error(self):
        self._set_key()
        with patch(POST, return_value=fake_response('no json here')):
            with self.assertRaises(UserError):
                self.book.action_suggest_categories()
