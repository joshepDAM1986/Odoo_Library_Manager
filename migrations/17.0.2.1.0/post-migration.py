def migrate(cr, version):
    """Los préstamos en curso de libros ya marcados como perdidos pasan a 'lost'."""
    cr.execute("""
        UPDATE library_loan l
           SET state = 'lost'
          FROM library_book b
         WHERE b.id = l.book_id
           AND b.state = 'lost'
           AND l.state = 'ongoing'
    """)
