from odoo.tests.common import TransactionCase


class TestAuthor(TransactionCase):

    def test_print_button_returns_the_report(self):
        author = self.env['library.author'].create({'name': 'Print Test'})
        # En una base nueva el diseño de documentos no está configurado y, para
        # el admin, report_action abre antes el asistente de configuración.
        action = author.with_context(discard_logo_check=True).action_print_report()
        self.assertEqual(action['type'], 'ir.actions.report')
        self.assertEqual(
            action['report_name'],
            'library_manager.report_library_author_document')