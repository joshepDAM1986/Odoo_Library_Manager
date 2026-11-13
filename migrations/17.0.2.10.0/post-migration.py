import logging

from odoo import SUPERUSER_ID, api
from odoo.exceptions import ValidationError


_logger = logging.getLogger(__name__)
_DNI_LETTERS = 'TRWAGMYFPDXBNJZSQVHLCKE'


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for index in range(1, 54):
        member = env.ref(
            f'library_manager.member_demo_{index}',
            raise_if_not_found=False,
        )
        if not member or member._name != 'library.member':
            continue
        partner = member.partner_id
        if partner.vat:
            continue

        number = 12345669 + index
        vat = f'{number:08d}{_DNI_LETTERS[number % 23]}'
        try:
            partner.write({'vat': vat})
        except ValidationError:
            _logger.info(
                'Skipped demo DNI %s for %s because another member uses it.',
                vat,
                partner.display_name,
            )
