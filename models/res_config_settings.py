from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .loan import DEFAULT_GRACE_DAYS, DEFAULT_LOAN_DAYS


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Los campos con config_parameter se guardan solos en ir.config_parameter
    # al pulsar Guardar; se mantienen las mismas claves que ya usaba el módulo
    # para no romper instalaciones existentes.
    library_gemini_api_key = fields.Char(
        string='Gemini API Key',
        config_parameter='library_manager.gemini_api_key',
        help='API key created in Google AI Studio. Without a key the AI '
             'category suggestion is disabled and the rest of the module '
             'keeps working.',
    )
    library_gemini_model = fields.Char(
        string='Gemini Model',
        config_parameter='library_manager.gemini_model',
        help='Model used for the AI category suggestion. '
             'The default is gemini-3.5-flash-lite.',
    )
    library_loan_days = fields.Integer(
        string='Default Loan Period (days)',
        default=DEFAULT_LOAN_DAYS,
        config_parameter='library_manager.loan_days',
        help='Days a new loan lasts by default. Loans that already exist '
             'keep their own due date.',
    )
    library_grace_days = fields.Integer(
        string='Grace Period Before Suspension (days)',
        default=DEFAULT_GRACE_DAYS,
        config_parameter='library_manager.grace_days',
        help='Days after the due date before the daily job suspends the '
             'member. Overdue notices are still sent from the due date.',
    )

    @api.constrains('library_loan_days', 'library_grace_days')
    def _check_library_settings(self):
        for settings in self:
            if settings.library_loan_days < 1:
                raise ValidationError(
                    _('The loan period must be at least 1 day.'))
            if settings.library_grace_days < 0:
                raise ValidationError(
                    _('The grace period cannot be negative.'))
