from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


class TestBookStates(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Book = cls.env['library.book']

    # --- flujo de estados -------------------------------------------------
    def test_cannot_borrow_unavailable_book(self):
        book = self.Book.create({'name': 'Test book', 'state': 'borrowed'})
        with self.assertRaises(UserError):
            book.action_borrow()

    def test_borrow_and_return(self):
        book = self.Book.create({'name': 'Test book'})
        self.assertEqual(book.state, 'available')

        book.action_borrow()
        self.assertEqual(book.state, 'borrowed')

        book.action_return()
        self.assertEqual(book.state, 'available')

    def test_cannot_return_available_book(self):
        book = self.Book.create({'name': 'Test book'})
        with self.assertRaises(UserError):
            book.action_return()

    def test_mark_lost_and_recover(self):
        book = self.Book.create({'name': 'Test book'})
        book.action_mark_lost()
        self.assertEqual(book.state, 'lost')
        book.action_recover()
        self.assertEqual(book.state, 'available')

    def test_cannot_mark_lost_twice(self):
        book = self.Book.create({'name': 'Test book', 'state': 'lost'})
        with self.assertRaises(UserError):
            book.action_mark_lost()

    def test_cannot_recover_available_book(self):
        book = self.Book.create({'name': 'Test book'})
        with self.assertRaises(UserError):
            book.action_recover()

    # --- restricciones ----------------------------------------------------
    def test_publication_year_in_the_future(self):
        with self.assertRaises(ValidationError):
            self.Book.create({'name': 'Future book', 'publication_year': 3000})

    def test_publication_year_valid(self):
        book = self.Book.create({'name': 'Old book', 'publication_year': 1605})
        self.assertEqual(book.publication_year, 1605)

    def test_isbn_must_be_unique(self):
        self.Book.create({'name': 'Book A', 'isbn': '1234567890'})
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'), self.cr.savepoint():
            self.Book.create({'name': 'Book B', 'isbn': '1234567890'})

    def test_pages_cannot_be_negative(self):
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'), self.cr.savepoint():
            self.Book.create({'name': 'Negative book', 'pages': -5})
