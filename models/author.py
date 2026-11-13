import logging
import re
import unicodedata
from datetime import date, datetime
import time

import requests

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, UserError, ValidationError


_logger = logging.getLogger(__name__)

OPEN_LIBRARY_AUTHOR_URL = 'https://openlibrary.org/authors/%s.json'
OPEN_LIBRARY_AUTHOR_SEARCH_URL = 'https://openlibrary.org/search/authors.json'
OPEN_LIBRARY_TIMEOUT = 30


class LibraryAuthor(models.Model):
    _name = 'library.author'
    _description = 'Library Author'
    _order = 'name'

    name = fields.Char(string='Author Name', required=True, index=True)
    openlibrary_key = fields.Char(
        string='Open Library ID',
        index=True,
        copy=False,
        help='Open Library author key (for example, OL23919A). Set it '
             'manually to link an existing author when their name differs.',
    )
    birth_date = fields.Date(string='Birth Date')
    bio = fields.Text(string='Biography')

    # One2many relacion con los libros
    book_ids = fields.One2many(
        'library.book',
        'author_id',
        string='Books',
    )

    # Contador dinamico de libros de cada autor
    book_count = fields.Integer(string='Book Count', compute='_compute_book_count')

    total_pages = fields.Integer(
        string='Total Pages Written',
        compute='_compute_total_pages',
        store=True,
    )

    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'The author name must be unique.'),
        ('openlibrary_key_unique', 'UNIQUE(openlibrary_key)',
         'The Open Library ID must be unique.'),
    ]

    @api.depends('book_ids')
    def _compute_book_count(self):
        data = self.env['library.book']._read_group(
            [('author_id', 'in', self.ids)], ['author_id'], ['__count'])
        counts = {author.id: count for author, count in data}
        for author in self:
            author.book_count = counts.get(author.id, 0)

    @api.depends('book_ids.pages')
    def _compute_total_pages(self):
        for author in self:
            author.total_pages = sum(author.book_ids.mapped('pages'))

    @api.model
    def _normalize_openlibrary_name(self, name):
        decomposed = unicodedata.normalize('NFKD', name or '')
        without_accents = ''.join(
            char for char in decomposed
            if not unicodedata.combining(char)
        )
        return ''.join(
            char for char in without_accents.casefold() if char.isalnum()
        )

    @api.model
    def _openlibrary_author_key(self, reference):
        match = re.search(
            r'(?:/authors/)?(OL\d+A)(?:\.json)?(?:/.*)?$',
            reference or '',
        )
        return match.group(1) if match else False

    @api.model
    def _fetch_open_library_author(self, author_key):
        try:
            if self.env.context.get('openlibrary_bulk_refresh'):
                time.sleep(1)
            response = requests.get(
                OPEN_LIBRARY_AUTHOR_URL % author_key,
                timeout=OPEN_LIBRARY_TIMEOUT,
            )
            if not response.ok:
                _logger.warning(
                    'Open Library author lookup failed with HTTP %s: %s',
                    response.status_code,
                    author_key,
                )
                return {}
            result = response.json()
            return result if isinstance(result, dict) else {}
        except (requests.exceptions.RequestException, ValueError):
            _logger.warning(
                'Could not retrieve Open Library author %s',
                author_key,
                exc_info=True,
            )
            return {}

    @api.model
    def _search_open_library_author_key(self, name):
        try:
            if self.env.context.get('openlibrary_bulk_refresh'):
                time.sleep(1)
            response = requests.get(
                OPEN_LIBRARY_AUTHOR_SEARCH_URL,
                params={'q': name},
                timeout=OPEN_LIBRARY_TIMEOUT,
            )
            response.raise_for_status()
            result = response.json()
        except requests.exceptions.Timeout:
            raise UserError(_('Open Library author search timed out. Try again.'))
        except (requests.exceptions.RequestException, ValueError):
            _logger.warning('Open Library author search failed', exc_info=True)
            raise UserError(_('Could not search Open Library for this author.'))

        query = self._normalize_openlibrary_name(name)
        matches = []
        for item in (result.get('docs') or []) if isinstance(result, dict) else []:
            if not isinstance(item, dict):
                continue
            alternate_names = item.get('alternate_names') or []
            if isinstance(alternate_names, str):
                alternate_names = [alternate_names]
            item_names = [item.get('name')] + alternate_names
            normalized_names = {
                self._normalize_openlibrary_name(candidate)
                for candidate in item_names
                if isinstance(candidate, str)
            }
            key = self._openlibrary_author_key(item.get('key'))
            if key and query in normalized_names:
                matches.append(key)

        matches = list(dict.fromkeys(matches))
        if not matches:
            raise UserError(_(
                "Open Library could not find an exact author match for '%s'."
            ) % name)
        if len(matches) > 1:
            raise UserError(_(
                "Open Library found multiple author matches for '%s'. "
                "Enter the correct Open Library ID on this author first."
            ) % name)
        return matches[0]

    @api.model
    def _openlibrary_birth_date(self, value):
        if not isinstance(value, str):
            return False
        value = value.strip()
        for date_format in (
            '%Y-%m-%d', '%d %B %Y', '%B %d, %Y', '%d %b %Y', '%b %d, %Y',
        ):
            try:
                parsed = datetime.strptime(value, date_format).date()
                return parsed.isoformat() if parsed <= date.today() else False
            except ValueError:
                continue
        return False

    @api.model
    def _openlibrary_bio(self, value):
        if isinstance(value, dict):
            value = value.get('value')
        return value.strip() if isinstance(value, str) and value.strip() else False

    def action_fill_from_openlibrary(self):
        self.ensure_one()
        if not self.env.su and not self.env.user.has_group(
            'library_manager.group_library_manager'
        ):
            raise AccessError(_('Only librarians can use author autofill.'))

        author_key = self._openlibrary_author_key(self.openlibrary_key)
        if not author_key:
            author_key = self._search_open_library_author_key(self.name)
        author_data = self._fetch_open_library_author(author_key)
        if not author_data:
            raise UserError(_(
                'Open Library did not return data for author ID %s.'
            ) % author_key)

        values = {'openlibrary_key': author_key}
        remote_name = (author_data.get('name') or '').strip()
        if remote_name and remote_name != self.name:
            collision = self.search([
                ('name', '=ilike', remote_name),
                ('id', '!=', self.id),
            ], limit=1)
            if collision:
                raise UserError(_(
                    "Open Library author '%s' conflicts with another local "
                    'author. Resolve the duplicate and retry.'
                ) % remote_name)
            values['name'] = remote_name

        birth_date = self._openlibrary_birth_date(
            author_data.get('birth_date')
        )
        if birth_date:
            values['birth_date'] = birth_date
        bio = self._openlibrary_bio(author_data.get('bio'))
        if bio:
            values['bio'] = bio
        self.write(values)

        updated = []
        if 'name' in values:
            updated.append(_('name'))
        if 'birth_date' in values:
            updated.append(_('birth date'))
        if 'bio' in values:
            updated.append(_('biography'))
        message = (
            _('Updated from Open Library: %s.') % ', '.join(updated)
            if updated else _('Open Library ID saved; no new author details were available.')
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Author Autofill'),
                'message': message,
                'type': 'success' if updated else 'warning',
                'sticky': False,
            },
        }

    def action_queue_openlibrary_refresh(self):
        if not self:
            raise UserError(_('Select at least one author to refresh.'))
        if not self.env.su and not self.env.user.has_group(
            'library_manager.group_library_manager'
        ):
            raise AccessError(_('Only librarians can queue author refreshes.'))

        Queue = self.env['library.metadata.refresh'].sudo()
        existing_ids = set(Queue.search([
            ('state', 'in', ['queued', 'processing']),
            ('author_id', 'in', self.ids),
        ]).mapped('author_id').ids)
        to_queue = self.filtered(lambda author: author.id not in existing_ids)
        if to_queue:
            Queue.create([{'author_id': author.id} for author in to_queue])

        if not to_queue:
            message = _('The selected authors already have queued refreshes.')
        else:
            message = _(
                'Queued %s author refreshes. Check Configuration > Open Library Refreshes for progress.'
            ) % len(to_queue)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Open Library Refresh'),
                'message': message,
                'type': 'success' if to_queue else 'warning',
                'sticky': False,
            },
        }

    def action_view_author_books(self):
        self.ensure_one()
        return {
            'name': _('Books'),
            'type': 'ir.actions.act_window',
            'res_model': 'library.book',
            'view_mode': 'tree,form',
            'domain': [('author_id', '=', self.id)],
            'context': {'default_author_id': self.id},
        }

    def action_print_report(self):
        self.ensure_one()
        return self.env.ref('library_manager.action_report_library_author').report_action(self)

    @api.constrains('birth_date')
    def _check_birth_date(self):
        today = fields.Date.today()
        for author in self:
            if author.birth_date and author.birth_date > today:
                raise ValidationError(_("The birth date cannot be in the future!"))
