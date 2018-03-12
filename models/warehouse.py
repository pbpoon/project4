#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Created by pbpoon on 2018/2/6
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class Warehouse(models.Model):
    _name = 'stock.warehouse'
    _description = '仓库'

    name = fields.Char('名称', required=True, index=True)
    code = fields.Char('缩写名称', required=True, size=5, help="一般采用英文字母")
    company_id = fields.Many2one(
        'res.company', 'Company', default=lambda self: self.env['res.company']._company_default_get('stock.inventory'),
        index=True, readonly=True, required=True,
        help='The company is automatically set from your user preferences.')
    partner_id = fields.Many2one('res.partner', 'Address')
    view_location_id = fields.Many2one('stock.location', 'View Location', domain=[('usage', '=', 'view')],
                                       required=True, readonly=True)
    lot_stock_id = fields.Many2one('stock.location', 'Location Stock', domain=[('usage', '=', 'internal')],
                                   required=True)

    @api.model
    def create(self, vals):
        # create view location for warehouse then create all locations
        loc_vals = {'usage': 'view', 'name': _(vals.get('code'))}
        # 'location_id': self.env.ref('stock.stock_location_locations').id}
        if vals.get('company_id'):
            loc_vals['company_id'] = vals.get('company_id')
        vals['view_location_id'] = self.env['stock.location'].create(loc_vals).id

        # def_values = self.default_get(['reception_steps', 'delivery_steps'])
        # reception_steps = vals.get('reception_steps', def_values['reception_steps'])
        # delivery_steps = vals.get('delivery_steps', def_values['delivery_steps'])
        sub_locations = {
            'lot_stock_id': {'name': _('Stock'), 'active': True, 'usage': 'internal'},
            # 'wh_input_stock_loc_id': {'name': _('Input'), 'active': reception_steps != 'one_step',
            #                           'usage': 'internal'},
            # 'wh_qc_stock_loc_id': {'name': _('Quality Control'), 'active': reception_steps == 'three_steps',
            #                        'usage': 'internal'},
            # 'wh_output_stock_loc_id': {'name': _('Output'), 'active': delivery_steps != 'ship_only',
            #                            'usage': 'internal'},
            # 'wh_pack_stock_loc_id': {'name': _('Packing Zone'), 'active': delivery_steps == 'pick_pack_ship',
            #                          'usage': 'internal'},
        }
        for field_name, values in sub_locations.items():
            values['location_id'] = vals['view_location_id']
            if vals.get('company_id'):
                values['company_id'] = vals.get('company_id')
            vals[field_name] = self.env['stock.location'].with_context(active_test=False).create(values).id

        # actually create WH
        warehouse = super(Warehouse, self).create(vals)
        # # create sequences and operation types
        # new_vals = warehouse.create_sequences_and_picking_types()
        # warehouse.write(new_vals)  # TDE FIXME: use super ?
        # # create routes and push/procurement rules
        # route_vals = warehouse.create_routes()
        # warehouse.write(route_vals)
        # # update partner data if partner assigned
        # if vals.get('partner_id'):
        #     self._update_partner_data(vals['partner_id'], vals.get('company_id'))
        return warehouse


class Location(models.Model):
    _name = 'stock.location'
    _description = '库存位置'
    _parent_name = "location_id"
    _parent_store = True
    _parent_order = 'name'
    _order = 'parent_left'
    _rec_name = 'complete_name'

    name = fields.Char('位置名称', required=True, translate=True)
    complete_name = fields.Char("Full Location Name", compute='_compute_complete_name', store=True)
    active = fields.Boolean('Active', default=True,
                            help="By unchecking the active field, you may hide a location without deleting it.")
    usage = fields.Selection([
        ('supplier', 'Vendor Location'),
        ('view', 'View'),
        ('internal', 'Internal Location'),
        ('customer', 'Customer Location'),
        ('inventory', 'Inventory Loss'),
        ('procurement', 'Procurement'),
        ('production', 'Production'),
        ('transit', 'Transit Location')], string='Location Type',
        default='internal', index=True, required=True,
        help="* Vendor Location: Virtual location representing the source location for products coming from your vendors"
             "\n* View: Virtual location used to create a hierarchical structures for your warehouse, aggregating its child locations ; can't directly contain products"
             "\n* Internal Location: Physical locations inside your own warehouses,"
             "\n* Customer Location: Virtual location representing the destination location for products sent to your customers"
             "\n* Inventory Loss: Virtual location serving as counterpart for inventory operations used to correct stock levels (Physical inventories)"
             "\n* Procurement: Virtual location serving as temporary counterpart for procurement operations when the source (vendor or production) is not known yet. This location should be empty when the procurement scheduler has finished running."
             "\n* Production: Virtual counterpart location for production operations: this location consumes the raw material and produces finished products"
             "\n* Transit Location: Counterpart location that should be used in inter-company or inter-warehouses operations")
    location_id = fields.Many2one(
        'stock.location', 'Parent Location', index=True, ondelete='cascade',
        help="The parent location that includes this location. Example : The 'Dispatch Zone' is the 'Gate 1' parent location.")
    child_ids = fields.One2many('stock.location', 'location_id', 'Contains')
    partner_id = fields.Many2one('res.partner', 'Owner', help="Owner of the location if not internal")
    quant_ids = fields.One2many('stock.quant', 'location_id', '库存框')
    parent_left = fields.Integer('Left Parent', index=1)
    parent_right = fields.Integer('Right Parent', index=1)
    scrap_location = fields.Boolean('报废位置', default=False)

    @api.one
    @api.depends('name', 'location_id.name')
    def _compute_complete_name(self):
        """ Forms complete name of location from parent location to child location. """
        name = self.name
        current = self
        while current.location_id:
            current = current.location_id
            name = '%s/%s' % (current.name, name)
        self.complete_name = name

    def write(self, values):
        if 'usage' in values and values['usage'] == 'view':
            if self.mapped('quant_ids'):
                raise UserError(_("This location's usage cannot be changed to view as it contains products."))
        return super(Location, self).write(values)

    def should_bypass_reservation(self):
        self.ensure_one()
        return self.usage in ('supplier', 'customer', 'inventory', 'production') or self.scrap_location

    def get_child_location(self):
        self.ensure_one()
        return self.search([('location_id', 'child_of', self.id)])

    def get_available_product_lst(self):
        self.ensure_one()
        product_lst = self.get_child_location().mapped('quant_ids').filtered(lambda r: r.available_pcs > 0).mapped('product_id.id')
        return product_lst

    def get_all_product_lst(self):
        self.ensure_one()
