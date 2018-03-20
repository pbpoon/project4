# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.addons.base.res.res_partner import WARNING_MESSAGE, WARNING_HELP


class Partner(models.Model):
    _inherit = 'res.partner'

    currency_id = fields.Many2one("res.currency", string="Currency")
    state_id = fields.Many2one("res.country.state", string='State', ondelete='restrict')
    city_id = fields.Many2one('area.city', '城市')
    district_id = fields.Many2one('area.district', '市县/行政区')


class City(models.Model):
    _name = 'area.city'
    _description = '城市'

    name = fields.Char('城市', required=True, index=True)
    state = fields.Many2one('res.country.state', '省份')


class District(models.Model):
    _name = 'area.district'
    _description = '市县/行政区'

    name = fields.Char('城市', required=True, index=True)
    city = fields.Many2one('area.city', '市县/行政区', required=True)
