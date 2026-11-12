import base64
from unittest.mock import MagicMock, patch

import requests

from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

GET = 'odoo.addons.library_manager.models.book.requests.get'

ISBN_13 = '9780140328721'
ISBN_10 = '0306406152'

# GIF 1x1 transparente: fields.Image valida que el contenido sea una imagen.
PNG_BASE64 = (
    'R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
)
PNG_BYTES = base64.b64decode(PNG_BASE64)


def open_library_response(isbn=ISBN_13, **overrides):
    """Respuesta simulada de Open Library (jscmd=data)."""
    data = {
        'title': 'Fantastic Mr. Fox',
        'authors': [{'name': 'Roald Dahl'}],
        'publish_date': '1988',
        'number_of_pages': 96,
        'cover': {'medium': 'https://covers.openlibrary.org/b/id/1-M.jpg'},
    }
    data.update(overrides)
    response = MagicMock()
    response.ok = True
    response.status_code = 200
    response.json.return_value = {f'ISBN:{isbn}': data}
    return response


def cover_response(content=PNG_BYTES, content_type='image/gif'):
    response = MagicMock()
    response.ok = True
    response.status_code = 200
    response.content = content
    response.headers = {'Content-Type': content_type}
    return response


class TestIsbnAutofill(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Book = cls.env['library.book']
        cls.Author = cls.env['library.author']
        cls.book = cls.Book.create({
            'name': 'Fantastic Mr. Fox',
            'isbn': '978-0-14-032872-1',
        })

    # --- validación del ISBN ---------------------------------------------
    def test_isbn_is_normalized(self):
        self.assertEqual(
            self.book._normalize_isbn(' 978-0-14 032872-1 '), ISBN_13)

    def test_valid_isbn_13(self):
        self.assertTrue(self.book._is_valid_isbn(ISBN_13))

    def test_valid_isbn_10(self):
        self.assertTrue(self.book._is_valid_isbn(ISBN_10))
        self.assertTrue(self.book._is_valid_isbn('097522980X'))

    def test_invalid_isbn_check_digit(self):
        self.assertFalse(self.book._is_valid_isbn('9780140328722'))
        self.assertFalse(self.book._is_valid_isbn('0306406153'))

    def test_invalid_isbn_length_or_prefix(self):
        self.assertFalse(self.book._is_valid_isbn('12345'))
        self.assertFalse(self.book._is_valid_isbn('1234567890123'))

    # --- autorrelleno ------------------------------------------------------
    def test_fills_empty_fields(self):
        with patch(GET, side_effect=[
            open_library_response(), cover_response(),
        ]):
            action = self.book.action_fill_from_isbn()

        self.assertEqual(self.book.isbn, ISBN_13)
        self.assertEqual(self.book.author_id.name, 'Roald Dahl')
        self.assertEqual(self.book.publication_year, 1988)
        self.assertEqual(self.book.pages, 96)
        self.assertTrue(self.book.cover_image)
        self.assertEqual(action['tag'], 'display_notification')
        self.assertEqual(action['params']['type'], 'success')

    def test_does_not_overwrite_existing_values(self):
        book = self.Book.create({
            'name': 'My own title',
            'isbn': ISBN_13,
            'author_id': self.Author.create({'name': 'Known Author'}).id,
            'publication_year': 2001,
            'pages': 20,
            'cover_image': PNG_BASE64,
        })
        cover_before = book.cover_image
        with patch(GET, return_value=open_library_response()) as mock_get:
            action = book.action_fill_from_isbn()

        self.assertEqual(book.name, 'My own title')
        self.assertEqual(book.author_id.name, 'Known Author')
        self.assertEqual(book.publication_year, 2001)
        self.assertEqual(book.pages, 20)
        self.assertEqual(book.cover_image, cover_before)
        self.assertEqual(mock_get.call_count, 1)
        self.assertEqual(action['params']['type'], 'warning')

    def test_creates_the_author_when_it_does_not_exist(self):
        with patch(GET, side_effect=[
            open_library_response(), cover_response(),
        ]):
            self.book.action_fill_from_isbn()
        self.assertEqual(
            self.Author.search_count([('name', '=', 'Roald Dahl')]), 1)

    def test_reuses_an_existing_author_ignoring_case(self):
        author = self.Author.create({'name': 'roald dahl'})
        with patch(GET, side_effect=[
            open_library_response(), cover_response(),
        ]):
            self.book.action_fill_from_isbn()
        self.assertEqual(self.book.author_id, author)
        self.assertEqual(
            self.Author.search_count(
                [('name', '=ilike', 'Roald Dahl')]), 1)

    def test_book_without_cover_in_the_response(self):
        with patch(GET, return_value=open_library_response(
            cover=None)) as mock_get:
            action = self.book.action_fill_from_isbn()
        self.assertFalse(self.book.cover_image)
        self.assertEqual(mock_get.call_count, 1)
        self.assertEqual(action['params']['type'], 'success')

    def test_cover_failure_does_not_block_the_metadata(self):
        with patch(GET, side_effect=[
            open_library_response(),
            requests.exceptions.ConnectionError(),
        ]):
            action = self.book.action_fill_from_isbn()
        self.assertEqual(self.book.author_id.name, 'Roald Dahl')
        self.assertEqual(self.book.publication_year, 1988)
        self.assertEqual(self.book.pages, 96)
        self.assertFalse(self.book.cover_image)
        self.assertEqual(action['params']['type'], 'warning')

    def test_new_record_is_created_with_the_title(self):
        book = self.Book.new({'isbn': '978-0-14-032872-1'})
        with patch(GET, side_effect=[
            open_library_response(), cover_response(),
        ]):
            action = book.action_fill_from_isbn()

        self.assertEqual(action['res_model'], 'library.book')
        created = self.Book.browse(action['res_id'])
        self.assertEqual(created.name, 'Fantastic Mr. Fox')
        self.assertEqual(created.isbn, ISBN_13)
        self.assertEqual(created.author_id.name, 'Roald Dahl')
        self.assertEqual(created.publication_year, 1988)
        self.assertEqual(created.pages, 96)
        self.assertTrue(created.cover_image)

    # --- errores -----------------------------------------------------------
    def test_missing_isbn_is_rejected_without_calling_the_api(self):
        book = self.Book.create({'name': 'No ISBN'})
        with patch(GET) as mock_get:
            with self.assertRaises(UserError):
                book.action_fill_from_isbn()
        mock_get.assert_not_called()

    @mute_logger('odoo.addons.library_manager.models.book')
    def test_invalid_isbn_is_rejected_without_calling_the_api(self):
        book = self.Book.create({
            'name': 'Bad ISBN', 'isbn': '9780140328722'})
        with patch(GET) as mock_get:
            with self.assertRaises(UserError):
                book.action_fill_from_isbn()
        mock_get.assert_not_called()

    @mute_logger('odoo.addons.library_manager.models.book')
    def test_duplicate_isbn_is_rejected_without_calling_the_api(self):
        self.Book.create({'name': 'Another copy', 'isbn': ISBN_13})
        with patch(GET) as mock_get:
            with self.assertRaises(UserError):
                self.book.action_fill_from_isbn()
        mock_get.assert_not_called()

    @mute_logger('odoo.addons.library_manager.models.book')
    def test_unknown_isbn_is_reported(self):
        response = MagicMock()
        response.ok = True
        response.status_code = 200
        response.json.return_value = {}
        with patch(GET, return_value=response):
            with self.assertRaises(UserError):
                self.book.action_fill_from_isbn()

    @mute_logger('odoo.addons.library_manager.models.book')
    def test_http_error_is_reported(self):
        response = MagicMock()
        response.ok = False
        response.status_code = 500
        with patch(GET, return_value=response):
            with self.assertRaises(UserError):
                self.book.action_fill_from_isbn()

    @mute_logger('odoo.addons.library_manager.models.book')
    def test_not_found_is_reported(self):
        response = MagicMock()
        response.ok = False
        response.status_code = 404
        with patch(GET, return_value=response):
            with self.assertRaises(UserError):
                self.book.action_fill_from_isbn()

    def test_timeout_is_reported(self):
        with patch(GET, side_effect=requests.exceptions.Timeout()):
            with self.assertRaises(UserError):
                self.book.action_fill_from_isbn()

    @mute_logger('odoo.addons.library_manager.models.book')
    def test_network_error_is_reported(self):
        with patch(GET,
                   side_effect=requests.exceptions.ConnectionError()):
            with self.assertRaises(UserError):
                self.book.action_fill_from_isbn()

    # --- permisos ----------------------------------------------------------
    def _user_in_group(self, login, group_xmlid):
        return self.env['res.users'].create({
            'name': login,
            'login': login,
            'groups_id': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref(group_xmlid).id,
            ])],
        })

    def test_reader_cannot_use_isbn_autofill(self):
        reader = self._user_in_group(
            'reader_isbn_test', 'library_manager.group_library_user')
        with patch(GET) as mock_get:
            with self.assertRaises(AccessError):
                self.book.with_user(
                    reader).action_fill_from_isbn()
        mock_get.assert_not_called()

    def test_librarian_can_use_isbn_autofill(self):
        librarian = self._user_in_group(
            'librarian_isbn_test',
            'library_manager.group_library_manager')
        with patch(GET, side_effect=[
            open_library_response(), cover_response(),
        ]):
            self.book.with_user(
                librarian).action_fill_from_isbn()
        self.assertEqual(self.book.author_id.name, 'Roald Dahl')
