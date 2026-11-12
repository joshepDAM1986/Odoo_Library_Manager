from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestLibrarySettings(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Settings = cls.env['res.config.settings']
        cls.Loan = cls.env['library.loan']
        cls.params = cls.env['ir.config_parameter'].sudo()
        cls.today = fields.Date.context_today(cls.Loan)
        cls.book = cls.env['library.book'].create({'name': 'Settings test book'})
        cls.member = cls.env['library.member'].create({'name': 'Settings member'})

    def _save(self, **kwargs):
        settings = self.Settings.create(kwargs)
        settings.execute()
        return settings

    def _new_loan(self, **kwargs):
        vals = {
            'book_id': self.book.id,
            'member_id': self.member.id,
        }
        vals.update(kwargs)
        return self.Loan.create(vals)

    def _overdue_loan(self, days_late=3):
        loan = self._new_loan(
            loan_date=self.today - timedelta(days=days_late + 7),
            due_date=self.today - timedelta(days=days_late),
        )
        loan.action_confirm()
        return loan

    # --- periodo de préstamo ----------------------------------------------
    def test_defaults_are_used_when_nothing_is_configured(self):
        loan = self._new_loan()
        self.assertEqual(loan.due_date, self.today + timedelta(days=14))

    def test_loan_period_is_used_for_new_loans(self):
        self._save(library_loan_days=21)
        loan = self._new_loan()
        self.assertEqual(loan.due_date, self.today + timedelta(days=21))

    def test_changing_the_period_does_not_move_existing_loans(self):
        loan = self._new_loan()
        self._save(library_loan_days=30)
        self.assertEqual(loan.due_date, self.today + timedelta(days=14))

    def test_invalid_loan_period_falls_back_to_the_default(self):
        self.params.set_param('library_manager.loan_days', 'not-a-number')
        loan = self._new_loan()
        self.assertEqual(loan.due_date, self.today + timedelta(days=14))

    def test_loan_period_must_be_positive(self):
        with self.assertRaises(ValidationError):
            self.Settings.create({'library_loan_days': 0})

    # --- gracia antes de suspender ----------------------------------------
    def test_no_suspension_during_the_grace_period(self):
        self._save(library_grace_days=5)
        self._overdue_loan(days_late=3)
        self.Loan._cron_suspend_overdue_members()
        self.assertEqual(self.member.state, 'active')

    def test_suspension_after_the_grace_period(self):
        self._save(library_grace_days=2)
        self._overdue_loan(days_late=3)
        self.Loan._cron_suspend_overdue_members()
        self.assertEqual(self.member.state, 'suspended')

    def test_suspension_on_the_grace_day_is_not_yet_due(self):
        # Con 5 días de gracia, un préstamo vencido hace exactamente 5 días
        # todavía no se suspende: la gracia es completa.
        self._save(library_grace_days=5)
        self._overdue_loan(days_late=5)
        self.Loan._cron_suspend_overdue_members()
        self.assertEqual(self.member.state, 'active')

    def test_grace_period_does_not_delay_the_overdue_email(self):
        self._save(library_grace_days=5)
        self.member.email = 'grace@example.com'
        loan = self._overdue_loan(days_late=1)
        self.Loan._cron_send_overdue_emails()
        mails = self.env['mail.mail'].search([
            ('model', '=', 'library.loan'), ('res_id', '=', loan.id)])
        self.assertEqual(len(mails), 1)

    def test_grace_period_cannot_be_negative(self):
        with self.assertRaises(ValidationError):
            self.Settings.create({'library_grace_days': -1})

    # --- pantalla de ajustes ----------------------------------------------
    def test_settings_screen_reads_the_stored_values(self):
        self._save(
            library_loan_days=10,
            library_grace_days=2,
            library_gemini_api_key='test-key',
            library_gemini_model='gemini-test',
        )
        values = self.Settings.default_get([
            'library_loan_days', 'library_grace_days',
            'library_gemini_api_key', 'library_gemini_model',
        ])
        self.assertEqual(values['library_loan_days'], 10)
        self.assertEqual(values['library_grace_days'], 2)
        self.assertEqual(values['library_gemini_api_key'], 'test-key')
        self.assertEqual(values['library_gemini_model'], 'gemini-test')

    def test_gemini_key_is_stored_in_the_existing_parameter(self):
        self._save(library_gemini_api_key='  test-key  ')
        self.assertEqual(
            self.params.get_param('library_manager.gemini_api_key'),
            'test-key')
