from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase


class TestLoan(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Loan = cls.env['library.loan']
        cls.today = fields.Date.context_today(cls.Loan)
        cls.book = cls.env['library.book'].create({'name': 'Loan test book'})
        cls.member = cls.env['library.member'].create({'name': 'Active Member'})
        cls.suspended = cls.env['library.member'].create({
            'name': 'Suspended Member', 'state': 'suspended'})

    def _new_loan(self, **kwargs):
        vals = {
            'book_id': self.book.id,
            'member_id': self.member.id,
            'due_date': self.today + timedelta(days=7),
        }
        vals.update(kwargs)
        return self.Loan.create(vals)

    # --- referencia y flujo -----------------------------------------------
    def test_reference_is_generated(self):
        loan = self._new_loan()
        self.assertTrue(loan.name.startswith('LN'))

    def test_confirm_borrows_the_book(self):
        loan = self._new_loan()
        loan.action_confirm()
        self.assertEqual(loan.state, 'ongoing')
        self.assertEqual(self.book.state, 'borrowed')

    def test_return_releases_the_book(self):
        loan = self._new_loan()
        loan.action_confirm()
        loan.action_return()
        self.assertEqual(loan.state, 'returned')
        self.assertEqual(loan.return_date, self.today)
        self.assertEqual(self.book.state, 'available')

    def test_cannot_confirm_for_suspended_member(self):
        loan = self._new_loan(member_id=self.suspended.id)
        with self.assertRaises(UserError):
            loan.action_confirm()
        self.assertEqual(loan.state, 'draft')
        self.assertEqual(self.book.state, 'available')

    def test_cannot_confirm_unavailable_book(self):
        self.book.action_mark_lost()
        loan = self._new_loan()
        with self.assertRaises(UserError):
            loan.action_confirm()
        self.assertEqual(loan.state, 'draft')

    def test_cannot_return_a_draft_loan(self):
        loan = self._new_loan()
        with self.assertRaises(UserError):
            loan.action_return()

    # --- cancelar ---------------------------------------------------------
    def test_cancel_draft_loan(self):
        loan = self._new_loan()
        loan.action_cancel()
        self.assertEqual(loan.state, 'cancelled')

    def test_cancel_ongoing_loan_releases_the_book(self):
        loan = self._new_loan()
        loan.action_confirm()
        loan.action_cancel()
        self.assertEqual(loan.state, 'cancelled')
        self.assertEqual(self.book.state, 'available')

    def test_cannot_cancel_returned_loan(self):
        loan = self._new_loan()
        loan.action_confirm()
        loan.action_return()
        with self.assertRaises(UserError):
            loan.action_cancel()

    # --- fechas -----------------------------------------------------------
    def test_due_date_before_loan_date_is_rejected(self):
        with self.assertRaises(ValidationError):
            self._new_loan(due_date=self.today - timedelta(days=1))

    def test_due_date_equal_to_loan_date_is_accepted(self):
        loan = self._new_loan(due_date=self.today)
        self.assertEqual(loan.due_date, loan.loan_date)

    def test_return_date_before_loan_date_is_rejected(self):
        loan = self._new_loan()
        with self.assertRaises(ValidationError):
            loan.write({'return_date': loan.loan_date - timedelta(days=1)})

    # --- borrado ----------------------------------------------------------
    def test_draft_loan_can_be_deleted(self):
        loan = self._new_loan()
        loan.unlink()
        self.assertFalse(loan.exists())

    def test_confirmed_loan_cannot_be_deleted(self):
        loan = self._new_loan()
        loan.action_confirm()
        with self.assertRaises(UserError):
            loan.unlink()

    # --- retraso ----------------------------------------------------------
    def test_days_overdue_for_ongoing_loan(self):
        loan = self._new_loan(
            loan_date=self.today - timedelta(days=10),
            due_date=self.today - timedelta(days=3))
        loan.action_confirm()
        self.assertEqual(loan.days_overdue, 3)

    def test_no_overdue_when_due_date_is_in_the_future(self):
        loan = self._new_loan()
        loan.action_confirm()
        self.assertEqual(loan.days_overdue, 0)

    def test_days_overdue_when_returned_late(self):
        loan = self._new_loan(
            loan_date=self.today - timedelta(days=10),
            due_date=self.today - timedelta(days=3))
        loan.action_confirm()
        loan.action_return()
        self.assertEqual(loan.days_overdue, 3)
