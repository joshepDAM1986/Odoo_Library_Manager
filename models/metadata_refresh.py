import logging
from datetime import timedelta

from odoo import _, api, fields, models


_logger = logging.getLogger(__name__)
REFRESH_BATCH_SIZE = 10
REFRESH_INTERVAL_SECONDS = 60
DEFAULT_REFRESH_SECONDS = 20


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
    started_at = fields.Datetime(readonly=True)
    processed_at = fields.Datetime(readonly=True)
    estimated_at = fields.Datetime(
        string='Estimated Processing Time',
        compute='_compute_estimated_at',
    )

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

    @api.depends('state', 'create_date', 'started_at', 'processed_at')
    def _compute_estimated_at(self):
        now = fields.Datetime.now()
        queued = self.search([('state', '=', 'queued')], order='id')
        positions = {job.id: position for position, job in enumerate(queued)}
        processing_count = self.search_count([('state', '=', 'processing')])
        completed = self.search([
            ('state', '=', 'done'), ('started_at', '!=', False),
            ('processed_at', '!=', False),
        ], order='processed_at desc', limit=20)
        durations = [
            (job.processed_at - job.started_at).total_seconds()
            for job in completed
            if job.processed_at and job.started_at
            and job.processed_at >= job.started_at
        ]
        average_seconds = (
            sum(durations) / len(durations) if durations
            else DEFAULT_REFRESH_SECONDS
        )

        cron = self.env.ref(
            'library_manager.ir_cron_library_metadata_refresh',
            raise_if_not_found=False,
        )
        nextcall = cron.nextcall if cron else False
        first_run = max(now, nextcall or now)
        first_run += timedelta(seconds=average_seconds * processing_count)

        for job in self:
            if job.state != 'queued' or job.id not in positions:
                job.estimated_at = False
                continue
            batch, offset = divmod(positions[job.id], REFRESH_BATCH_SIZE)
            job.estimated_at = first_run + timedelta(
                seconds=(batch * REFRESH_INTERVAL_SECONDS)
                + (offset * average_seconds)
            )

    @api.model
    def _cron_process_pending(self):
        """Process a small queue batch so metadata refreshes do not block users."""
        jobs = self.sudo().search(
            [('state', '=', 'queued')], order='id', limit=10
        )
        for job in jobs:
            try:
                with self.env.cr.savepoint():
                    job.write({
                        'state': 'processing',
                        'started_at': fields.Datetime.now(),
                    })
                    context = {
                        'openlibrary_bulk_refresh': True,
                    }
                    if job.requested_by.lang:
                        context['lang'] = job.requested_by.lang
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
                try:
                    failure_context = {}
                    if job.requested_by.lang:
                        failure_context['lang'] = job.requested_by.lang
                    if job.book_id:
                        book = job.book_id.with_context(**failure_context)
                        retained = book._openlibrary_local_fields_without_source(
                            set()
                        )
                        book._post_openlibrary_refresh_note(
                            {}, retained, lookup_error=str(exc)
                        )
                    elif job.author_id:
                        job.author_id.with_context(
                            **failure_context
                        )._apply_openlibrary_data(
                            False, {}, source_error=str(exc)
                        )
                except Exception:
                    _logger.exception(
                        'Could not post failure note for Open Library job %s',
                        job.id,
                    )
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
