from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


class TestLoanReport(TransactionCase):
    """library.loan.report es una vista SQL: aqui se comprueba que cuenta bien."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Loan = cls.env['library.loan']
        cls.Report = cls.env['library.loan.report']
        cls.today = fields.Date.context_today(cls.Loan)

        cls.author = cls.env['library.author'].create({'name': 'Report Author'})
        Book = cls.env['library.book']
        cls.popular = Book.create({'name': 'Popular', 'author_id': cls.author.id})
        cls.average = Book.create({'name': 'Average', 'author_id': cls.author.id})
        cls.never = Book.create({'name': 'Never borrowed', 'author_id': cls.author.id})
        cls.member = cls.env['library.member'].create({'name': 'Report Member'})

    def _returned_loan(self, book):
        loan = self.Loan.create({'book_id': book.id, 'member_id': self.member.id})
        loan.action_confirm()
        loan.action_return()
        return loan

    def _rows(self, book):
        self.env.flush_all()
        return self.Report.search([('book_id', '=', book.id)])

    def test_loans_are_counted_per_book(self):
        for _i in range(3):
            self._returned_loan(self.popular)
        self._returned_loan(self.average)
        self.assertEqual(sum(self._rows(self.popular).mapped('loan_count')), 3)
        self.assertEqual(sum(self._rows(self.average).mapped('loan_count')), 1)

    def test_book_without_loans_has_one_row_with_zero(self):
        rows = self._rows(self.never)
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows.loan_id)
        self.assertEqual(rows.loan_count, 0)

    def test_draft_and_cancelled_loans_are_not_counted(self):
        self.Loan.create({'book_id': self.never.id, 'member_id': self.member.id})
        cancelled = self.Loan.create({'book_id': self.never.id, 'member_id': self.member.id})
        cancelled.action_cancel()
        self.assertEqual(sum(self._rows(self.never).mapped('loan_count')), 0)

    def test_most_borrowed_book_has_the_better_rank(self):
        for _i in range(3):
            self._returned_loan(self.popular)
        self._returned_loan(self.average)
        popular = self._rows(self.popular)[0]
        average = self._rows(self.average)[0]
        self.assertLess(popular.book_top_rank, average.book_top_rank)

    def test_never_borrowed_book_comes_first_in_least_borrowed(self):
        self._returned_loan(self.popular)
        never = self._rows(self.never)[0]
        popular = self._rows(self.popular)[0]
        self.assertLess(never.book_low_rank, popular.book_low_rank)

    def test_overdue_loan_is_flagged(self):
        loan = self.Loan.create({
            'book_id': self.popular.id,
            'member_id': self.member.id,
            'loan_date': self.today - timedelta(days=20),
            'due_date': self.today - timedelta(days=5),
        })
        loan.action_confirm()
        self.env.flush_all()
        row = self.Report.search([('loan_id', '=', loan.id)])
        self.assertEqual(row.overdue_count, 1)
        self.assertEqual(row.days_late, 5)

    def test_report_is_read_only(self):
        # En una vista SQL no hay tabla donde escribir: crear no debe funcionar
        with self.assertRaises(Exception), mute_logger('odoo.sql_db'), self.cr.savepoint():
            self.Report.create({'book_id': self.popular.id})
