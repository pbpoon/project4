#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Created by pbpoon on 2018/2/6
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class Warehouse(models.Model):
    _name = 'stock.warehouse'
    _description = '仓库'

    name = fields.Char('名称', required=True, index=True)
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
        loc_vals = {'usage': 'view'}
        # 'name': _(vals.get('code')),
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


class PickingType(models.Model):
    _name = 'stock.picking.type'
    _description = '作业类型'

    name = fields.Char('作业名称', required=True)
    code = fields.Char('编码', required=True)
    default_location_src_id = fields.Many2one('stock.location', string='默认源库位置')
    default_location_dest_id = fields.Many2one('stock.location', string='默认目标库位置')
    warehouse_id = fields.Many2one('stock.warehouse', string='仓库')
    is_production = fields.Boolean('生产作业', default=False)
    orig_product_type = fields.Many2one('product.type', '原材料类型')
    product_type = fields.Many2one('product.type', '成品类型')


class Picking(models.Model):
    _name = 'stock.picking'
    _description = '作业单'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('单号', default='/', readonly=True)
    picking_type_id = fields.Many2one('stock.picking.type', '作业类型', required=True)
    default_location_src_id = fields.Many2one('stock.location', string='源库位置',
                                              related='picking_type_id.default_location_src_id')
    default_location_dest_id = fields.Many2one('stock.location', string='目标库位置',
                                               related='picking_type_id.default_location_dest_id')
    partner_id = fields.Many2one('res.partner', string='业务伙伴')
    date = fields.Datetime('日期', default=fields.datetime.now())
    move_ids = fields.One2many('stock.move', 'picking_id', '库存移动')
    state = fields.Selection(
        selection=(('draft', 'Draft'), ('waiting', 'Waiting'), ('confirm', 'Confirm'), ('done', 'Done')),
        string='Status', readonly=True, default='draft')
    order_line_ids = fields.One2many('stock.picking.line', 'picking_id', '作业明细行')

    @api.multi
    def _compute_state(self):
        for r in self:
            state_lst = r.move_ids.mapped('state')
            pass

    @api.multi
    def action_done(self):
        for record in self:
            record.move_ids._action_done()

    @api.multi
    def action_confirm(self):
        self.ensure_one()
        for line in self.order_line_ids:
            line._action_confirm()
        self.write({'state': 'confirm'})


class PickingLine(models.Model):
    _name = 'stock.picking.line'
    _description = '作业单明细'

    sequence = fields.Integer('序号', default=10)
    picking_id = fields.Many2one('stock.picking', '作业单', required=True, readonly=True)
    product_id = fields.Many2one('product.product', string='产品', required=True)
    location_id = fields.Many2one('stock.location', string='库存位置', required=True)
    location_dest_id = fields.Many2one('stock.location', string='目标库位置')
    part = fields.Integer('夹数', compute='_compute_qty', store=True)
    pcs = fields.Integer('件数', compute='_compute_qty', inverse='_set_pcs', store=True)
    reality_pcs = fields.Integer('实际件数')
    qty = fields.Float('数量', required=True, readonly=True, compute='_compute_qty', store=True)
    uom = fields.Many2one('product.uom', '单位', related='product_id.uom', readonly=True, store=True)
    package_list_id = fields.Many2one('package.list', '码单')
    unit_price = fields.Float('单价')
    amount = fields.Float('金额', compute='_compute_total')
    move_ids = fields.One2many('stock.move', 'picking_line_id', '库存移动', readonly=True)
    state = fields.Selection(
        selection=(('draft', 'Draft'), ('waiting', 'Waiting'), ('confirm', 'Confirm'), ('done', 'Done')),
        string='Status', readonly=True, default='draft', related='picking_id.state', store=True)
    purchase_line_id = fields.Many2one('purchase.order.line', '采购订单行', readonly=True)

    @api.depends('qty', 'unit_price')
    def _compute_total(self):
        for line in self:
            line.amount = line.qty * line.unit_price

    @api.depends('product_id.type', 'reality_pcs', 'product_id.single_qty')
    def _compute_qty(self):
        for r in self:
            if r.product_id.type == 'slab':
                r.qty = r.package_list_id.qty
                r.pcs = r.package_list_id.pcs
                r.part = r.package_list_id.part
            elif r.product_id.type == 'pbom':
                r.qty = r.product_id.single_qty * r.reality_pcs
                r.pcs = r.reality_pcs
            elif r.product_id.type == 'block':
                r.qty = r.product_id.single_qty
                r.pcs = 1

    @api.multi
    def _set_pcs(self):
        self.ensure_one()
        self.reality_pcs = self.pcs

    @api.multi
    def _prepare_stock_move(self):
        self.ensure_one()
        vals = {
            'product_id': self.product_id.id,
            'location_id': self.location_id.id,
            'location_dest_id': self.location_dest_id.id,
            'picking_line_id': self.id,
            'picking_id': self.picking_id.id,
            'pcs': self.pcs,
            'qty': self.qty,
        }

        if self.package_list_id:
            slab_ids = self.package_list_id.mapped('slab_ids.id')
            vals['slab_ids'] = [(6, 0, slab_ids)]
        return vals

    @api.multi
    def _create_stock_move(self):
        move = self.move_ids[0]
        vals = self._prepare_stock_move()
        if not move:
            move = self.env['stock.move'].create(vals)
        else:
            move.write(vals)

    @api.multi
    def _action_confirm(self):
        self.ensure_one()
        self._create_stock_move()


class StockMove(models.Model):
    _name = 'stock.move'
    _description = '库存移动作业'

    sequence = fields.Integer('序号', default=10)
    picking_line_id = fields.Many2one('stock.picking.line', '作业单明细行', required=True, readonly=True)
    picking_id = fields.Many2one('stock.picking', '作业单', related='picking_line_id.picking_id', required=True,
                                 readonly=True)
    orig_move_id = fields.Many2one('stock.move', string='源库存移动')
    location_id = fields.Many2one('stock.location', string='库存位置', related='picking_line_id.location_id', store=True)
    location_dest_id = fields.Many2one('stock.location', string='目标库位置', related='picking_line_id.location_dest_id',
                                       store=True)
    product_id = fields.Many2one('product.product', string='产品', required=True)
    pcs = fields.Integer('件数', required=True)
    part = fields.Integer('夹数', compute='_compute_part')
    qty = fields.Float('数量', required=True)
    uom = fields.Many2one('product.uom', '单位', related='product_id.uom', readonly=True, store=True)
    # package_list_id = fields.Many2one('package.list', '码单')
    slab_ids = fields.Many2many('product.slab', string='板材')
    state = fields.Selection(selection=(('draft', 'Draft'), ('confirm', 'Confirm'), ('done', 'Done')),
                             string='Status', readonly=True, default='draft')

    @api.depends('slab_ids')
    def _compute_part(self):
        for r in self:
            r.part = len(set(r.slab_ids.part_num))

    @api.multi
    def _action_done(self):
        quant = self.env['stock.quant']
        out_moves = self.env['stock.move']
        in_moves = self.env['stock.move']
        for move in self:
            out_moves |= move.filtered(lambda r: r.location_id.usage == 'internal')
            in_moves |= move.filtered(lambda r: r.location_dest_id.usage == 'internal')
        for om in out_moves:
            quant._update_available(om.product_id, om.location_id, -om.pcs, om.slab_ids)
        for im in in_moves:
            quant._update_available(im.product_id, im.location_dest_id, im.pcs, im.slab_ids)
        self.write({'state': 'done'})
        return True

# class StockRawMove(models.Model):
#     _name = 'stock.raw.move'
#     _description = '生产原材料库存作业'
#
#     location_id = fields.Many2one('stock.location', string='库位置')
#     location_dest_id = fields.Many2one('stock.location', string='默认目标库位置')
#     product_id = fields.Many2one('product', string='产品', required=True)
#     pcs = fields.Integer('件数', compute='_compute_qty')
#     part = fields.Integer('夹数', compute='_compute_qty')
