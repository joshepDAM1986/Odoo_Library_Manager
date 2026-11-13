import logging

from odoo import _, api, fields, models


_logger = logging.getLogger(__name__)


class LibraryMetadataRefresh(models.Model):
    _name = 'library.metadata.refresh'
    _description = 'Library Open Library Metadata Refresh'
    _order = 'id desc'

    name = fields.Char(compute='_compute_name', store=True)
    book_id = fields.Many2one(
        'library.book', ondelete='cascade', index=True,
    )
    author_id = fields.Many2one(
        'library.author', ondelete='cascade', index=True,
    )
    requested_by = fields.Many2one(
        'res.users', readonly=True, default=lambda self: self.env.user,
    )
    state = fields.Selection([
        ('queued', 'Queued'),
        ('processing', 'Processing'),
        ('done', 'Done'),
        ('failed', 'Failed'),
    ], required=True, default='queued', index=True, readonly=True)
    message = fields.Text(readonly=True)
    processed_at = fields.Datetime(readonly=True)

    _sql_constraints = [
        (
            'exactly_one_target',
            'CHECK ((book_id IS NOT NULL) <> (author_id IS NOT NULL))',
            'A refresh job must target exactly one book or author.',
        ),
    ]

    @api.depends('book_id.display_name', 'author_id.display_name')
    def _compute_name(self):
        for job in self:
            if job.book_id:
                job.name = _('Book: %s', job.book_id.display_name)
            elif job.author_id:
                job.name = _('Author: %s', job.author_id.display_name)
            else:
                job.name = _('Deleted record')

    @api.model
    def _cron_process_pending(self):
        """Process a small queue batch so metadata refreshes do not block users."""
        jobs = self.sudo().search(
            [('state', '=', 'queued')], order='id', limit=10
        )
        for job in jobs:
            try:
                with self.env.cr.savepoint():
                    job.write({'state': 'processing'})
                    context = {
                        'openlibrary_bulk_refresh': True,
                        'openlibrary_refresh_overwrite': True,
                    }
                    if job.book_id:
                        result = job.book_id.with_context(
                            **context
                        ).action_fill_from_isbn()
                        message = result.get('params', {}).get(
                            'message', _('Book metadata refreshed.')
                        ) if isinstance(result, dict) else _('Book metadata refreshed.')
                    elif job.author_id:
                        result = job.author_id.with_context(
                            **context
                        ).action_fill_from_openlibrary()
                        message = result.get('params', {}).get(
                            'message', _('Author metadata refreshed.')
                        ) if isinstance(result, dict) else _('Author metadata refreshed.')
                    else:
                        raise ValueError('Refresh target was deleted.')
            except Exception as exc:
                _logger.exception('Open Library refresh job %s failed', job.id)
                job.write({
                    'state': 'failed',
                    'message': str(exc) or _('Unexpected error. See the server log.'),
                    'processed_at': fields.Datetime.now(),
                })
            else:
                job.write({
                    'state': 'done',
                    'message': message,
                    'processed_at': fields.Datetime.now(),
                })
