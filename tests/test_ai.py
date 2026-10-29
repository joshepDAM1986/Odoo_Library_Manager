from unittest.mock import MagicMock, patch

import requests

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

POST = 'odoo.addons.library_manager.models.book.requests.post'


def gemini_response(text='[]', ok=True, status_code=200, error_message='error'):
    """Respuesta simulada de la API de Gemini (generateContent)."""
    response = MagicMock()
    response.ok = ok
    response.status_code = status_code
    if ok:
        response.json.return_value = {
            'candidates': [{'content': {'parts': [{'text': text}]}}]
        }
    else:
        response.json.return_value = {'error': {'message': error_message}}
    return response


class TestSuggestCategories(TransactionCase):
    """La API externa se simula con mock: los tests nunca hacen llamadas reales."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.fiction = cls.env['library.category'].create({'name': 'Test Fiction'})
        cls.history = cls.env['library.category'].create({'name': 'Test History'})
        cls.book = cls.env['library.book'].create({
            'name': 'AI test book', 'description': 'A made-up story.'})

    def _set_params(self, key='test-key', model=None):
        params = self.env['ir.config_parameter'].sudo()
        params.set_param('library_manager.gemini_api_key', key)
        if model:
            params.set_param('library_manager.gemini_model', model)

    # --- configuracion ----------------------------------------------------
    def test_requires_api_key(self):
        self._set_params(key='')
        with patch(POST) as mock_post:
            with self.assertRaises(UserError):
                self.book.action_suggest_categories()
        mock_post.assert_not_called()

    def test_rejects_invalid_model_name(self):
        self._set_params(model='../evil-path')
        with patch(POST) as mock_post:
            with self.assertRaises(UserError):
                self.book.action_suggest_categories()
        mock_post.assert_not_called()

    def test_api_key_goes_in_header_not_in_url(self):
        self._set_params()
        with patch(POST, return_value=gemini_response('["Test Fiction"]')) as mock_post:
            self.book.action_suggest_categories()
        args, kwargs = mock_post.call_args
        self.assertNotIn('test-key', args[0])
        self.assertEqual(kwargs['headers']['x-goog-api-key'], 'test-key')

    # --- respuestas correctas ---------------------------------------------
    def test_adds_suggested_categories(self):
        self._set_params()
        with patch(POST, return_value=gemini_response('["Test Fiction"]')):
            self.book.action_suggest_categories()
        self.assertEqual(self.book.category_ids, self.fiction)

    def test_keeps_existing_categories(self):
        self._set_params()
        self.book.category_ids = self.history
        with patch(POST, return_value=gemini_response('["Test Fiction"]')):
            self.book.action_suggest_categories()
        self.assertEqual(self.book.category_ids, self.fiction | self.history)

    def test_ignores_unknown_categories(self):
        self._set_params()
        with patch(POST, return_value=gemini_response('["Test History", "Does not exist"]')):
            self.book.action_suggest_categories()
        self.assertEqual(self.book.category_ids, self.history)

    def test_matching_ignores_case(self):
        self._set_params()
        with patch(POST, return_value=gemini_response('["test fiction"]')):
            self.book.action_suggest_categories()
        self.assertEqual(self.book.category_ids, self.fiction)

    def test_markdown_fences_are_removed(self):
        self._set_params()
        text = '```json\n["Test Fiction"]\n```'
        with patch(POST, return_value=gemini_response(text)):
            self.book.action_suggest_categories()
        self.assertEqual(self.book.category_ids, self.fiction)

    # --- respuestas incorrectas -------------------------------------------
    def test_invalid_json_raises_a_clear_error(self):
        self._set_params()
        with patch(POST, return_value=gemini_response('no json here')):
            with self.assertRaises(UserError):
                self.book.action_suggest_categories()

    def test_answer_that_is_not_a_list_raises_a_clear_error(self):
        self._set_params()
        with patch(POST, return_value=gemini_response('{"category": "Test Fiction"}')):
            with self.assertRaises(UserError):
                self.book.action_suggest_categories()

    def test_response_without_candidates_raises_a_clear_error(self):
        self._set_params()
        response = MagicMock()
        response.ok = True
        response.json.return_value = {'candidates': []}
        with patch(POST, return_value=response):
            with self.assertRaises(UserError):
                self.book.action_suggest_categories()

    # --- errores de red y HTTP --------------------------------------------
    def test_quota_error_is_reported(self):
        self._set_params()
        response = gemini_response(ok=False, status_code=429, error_message='quota')
        with patch(POST, return_value=response):
            with self.assertRaises(UserError):
                self.book.action_suggest_categories()

    def test_unknown_model_is_reported(self):
        self._set_params()
        response = gemini_response(ok=False, status_code=404, error_message='not found')
        with patch(POST, return_value=response):
            with self.assertRaises(UserError):
                self.book.action_suggest_categories()

    def test_timeout_is_reported(self):
        self._set_params()
        with patch(POST, side_effect=requests.exceptions.Timeout()):
            with self.assertRaises(UserError):
                self.book.action_suggest_categories()

    def test_network_error_is_reported(self):
        self._set_params()
        with patch(POST, side_effect=requests.exceptions.ConnectionError()):
            with self.assertRaises(UserError):
                self.book.action_suggest_categories()
