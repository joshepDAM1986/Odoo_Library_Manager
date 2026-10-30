from odoo import fields, models, tools


class LibraryLoanReport(models.Model):
    """Estadisticas de prestamos.

    Es un modelo de SOLO LECTURA respaldado por una vista SQL (_auto = False):
    no tiene tabla propia, Odoo no crea nada y los datos se calculan al vuelo
    a partir de library_book y library_loan. Es el patron de los informes
    estandar de Odoo (sale.report, account.invoice.report...).

    Una fila por prestamo (en curso o devuelto) y, ademas, una fila por cada
    libro que nunca se ha prestado (loan_id vacio y loan_count = 0), para
    poder ver tambien los libros "menos prestados".
    """
    _name = 'library.loan.report'
    _description = 'Loan Statistics'
    _auto = False
    _rec_name = 'book_id'
    _order = 'loan_date desc'

    book_id = fields.Many2one('library.book', string='Book', readonly=True)
    author_id = fields.Many2one('library.author', string='Author', readonly=True)
    member_id = fields.Many2one('library.member', string='Member', readonly=True)
    loan_id = fields.Many2one('library.loan', string='Loan', readonly=True)

    loan_date = fields.Date(string='Loan Date', readonly=True)
    due_date = fields.Date(string='Due Date', readonly=True)
    return_date = fields.Date(string='Return Date', readonly=True)
    loan_state = fields.Selection([
        ('ongoing', 'Ongoing'),
        ('returned', 'Returned'),
    ], string='Loan Status', readonly=True)

    # Medidas (lo que se suma / promedia en los graficos)
    loan_count = fields.Integer(string='Loans', readonly=True)
    overdue_count = fields.Integer(string='Overdue Loans', readonly=True)
    days_late = fields.Float(
        string='Avg Days Late', readonly=True, digits=(16, 1), group_operator='avg')

    # Posiciones en los "rankings" (1 = el mas prestado). Solo se usan en los
    # dominios de las acciones para quedarse con el top 10 y que los graficos
    # sean legibles aunque haya miles de libros.
    book_top_rank = fields.Integer(string='Book Rank (most borrowed)', readonly=True, group_operator='min')
    book_low_rank = fields.Integer(string='Book Rank (least borrowed)', readonly=True, group_operator='min')
    author_rank = fields.Integer(string='Author Rank', readonly=True, group_operator='min')
    member_rank = fields.Integer(string='Member Rank', readonly=True, group_operator='min')

    def _query(self):
        return """
            WITH book_totals AS (
                SELECT b.id AS book_id, b.author_id AS author_id, COUNT(l.id) AS total
                  FROM library_book b
             LEFT JOIN library_loan l
                    ON l.book_id = b.id AND l.state IN ('ongoing', 'returned')
              GROUP BY b.id, b.author_id
            ),
            book_ranks AS (
                SELECT book_id,
                       RANK() OVER (ORDER BY total DESC) AS top_rank,
                       ROW_NUMBER() OVER (ORDER BY total ASC, book_id) AS low_rank
                  FROM book_totals
            ),
            author_ranks AS (
                SELECT author_id,
                       RANK() OVER (ORDER BY SUM(total) DESC) AS author_rank
                  FROM book_totals
                 WHERE author_id IS NOT NULL
              GROUP BY author_id
            ),
            member_ranks AS (
                SELECT member_id,
                       RANK() OVER (ORDER BY COUNT(*) DESC) AS member_rank
                  FROM library_loan
                 WHERE state IN ('ongoing', 'returned')
              GROUP BY member_id
            )
            SELECT
                ROW_NUMBER() OVER (ORDER BY b.id, l.id) AS id,
                b.id AS book_id,
                b.author_id AS author_id,
                l.id AS loan_id,
                l.member_id AS member_id,
                l.loan_date AS loan_date,
                l.due_date AS due_date,
                l.return_date AS return_date,
                l.state AS loan_state,
                CASE WHEN l.id IS NULL THEN 0 ELSE 1 END AS loan_count,
                CASE WHEN l.state = 'ongoing' AND l.due_date < CURRENT_DATE
                     THEN 1 ELSE 0 END AS overdue_count,
                CASE WHEN l.id IS NULL THEN NULL
                     ELSE GREATEST(COALESCE(l.return_date, CURRENT_DATE) - l.due_date, 0)
                END AS days_late,
                br.top_rank AS book_top_rank,
                br.low_rank AS book_low_rank,
                ar.author_rank AS author_rank,
                mr.member_rank AS member_rank
              FROM library_book b
              JOIN book_ranks br ON br.book_id = b.id
         LEFT JOIN author_ranks ar ON ar.author_id = b.author_id
         LEFT JOIN library_loan l
                ON l.book_id = b.id AND l.state IN ('ongoing', 'returned')
         LEFT JOIN member_ranks mr ON mr.member_id = l.member_id
        """

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            "CREATE OR REPLACE VIEW %s AS (%s)" % (self._table, self._query()))
