from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestBookStates(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Book = cls.env['library.book']

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