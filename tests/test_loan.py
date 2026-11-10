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

    # --- libro perdido con el préstamo en curso ---------------------------
    def test_mark_lost_closes_the_ongoing_loan(self):
        loan = self._new_loan()
        loan.action_confirm()
        self.book.action_mark_lost()
        self.assertEqual(loan.state, 'lost')
        self.assertEqual(self.book.state, 'lost')

    def test_lost_loan_cannot_be_returned_or_cancelled(self):
        loan = self._new_loan()
        loan.action_confirm()
        self.book.action_mark_lost()
        with self.assertRaises(UserError):
            loan.action_return()
        with self.assertRaises(UserError):
            loan.action_cancel()

    def test_recovering_the_book_keeps_the_loan_as_lost(self):
        loan = self._new_loan()
        loan.action_confirm()
        self.book.action_mark_lost()
        self.book.action_recover()
        self.assertEqual(loan.state, 'lost')
        self.assertEqual(self.book.state, 'available')

    def test_lost_loan_is_not_overdue(self):
        loan = self._new_loan(
            loan_date=self.today - timedelta(days=10),
            due_date=self.today - timedelta(days=3))
        loan.action_confirm()
        self.book.action_mark_lost()
        self.assertEqual(loan.days_overdue, 0)

    def test_lost_loan_cannot_be_deleted(self):
        loan = self._new_loan()
        loan.action_confirm()
        self.book.action_mark_lost()
        with self.assertRaises(UserError):
            loan.unlink()

    # --- aviso de retraso (cron) ------------------------------------------
    def _overdue_loan(self, email='member@example.com'):
        self.member.email = email
        loan = self._new_loan(
            loan_date=self.today - timedelta(days=10),
            due_date=self.today - timedelta(days=3))
        loan.action_confirm()
        return loan

    def _mails_for(self, loan):
        return self.env['mail.mail'].search([
            ('model', '=', 'library.loan'), ('res_id', '=', loan.id)])

    def test_cron_is_unlimited_and_active(self):
        # Sin numbercall=-1 el cron se ejecutaría una sola vez y se desactivaría
        cron = self.env.ref('library_manager.ir_cron_library_overdue_email')
        self.assertEqual(cron.numbercall, -1)
        self.assertTrue(cron.active)

    def test_cron_sends_one_notice_per_overdue_loan(self):
        loan = self._overdue_loan()
        self.Loan._cron_send_overdue_emails()
        self.assertEqual(len(self._mails_for(loan)), 1)
        self.assertTrue(loan.overdue_email_sent_at)
        # Una segunda ejecución no vuelve a avisar
        self.Loan._cron_send_overdue_emails()
        self.assertEqual(len(self._mails_for(loan)), 1)

    def test_cron_skips_members_without_email(self):
        loan = self._overdue_loan(email=False)
        self.Loan._cron_send_overdue_emails()
        self.assertFalse(self._mails_for(loan))
        self.assertFalse(loan.overdue_email_sent_at)

    def test_cron_ignores_lost_loans(self):
        loan = self._overdue_loan()
        self.book.action_mark_lost()
        self.Loan._cron_send_overdue_emails()
        self.assertFalse(self._mails_for(loan))

    def test_changing_due_date_resets_the_overdue_notice(self):
        loan = self._overdue_loan()
        self.Loan._cron_send_overdue_emails()
        self.assertTrue(loan.overdue_email_sent_at)
        loan.due_date = self.today + timedelta(days=5)
        self.assertFalse(loan.overdue_email_sent_at)
