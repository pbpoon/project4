# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.addons.base.res.res_partner import WARNING_MESSAGE, WARNING_HELP


class Partner(models.Model):
    _inherit = 'res.partner'

    currency_id = fields.Many2one("res.currency", string="Currency")
