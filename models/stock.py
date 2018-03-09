#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Created by pbpoon on 2018/2/6
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

PRODUCT_TYPE_SELECTION = [
    ('block', '荒料'),
    ('slab', '板材'),
    ('pbom', '毛板')
]


class AbsComputeQty(object):

    @api.model
    def create(self, vals):
        if vals.get('package_list_id') and vals.get('pcs'):
            package_list = self.env['package.list'].browse(vals['package_list_id'])
            vals.update({
                'qty': package_list.qty,
                'pcs': package_list.pcs,
                'part': package_list.part,
            })

        elif vals.get('pcs') and vals.get('product_id'):
            product = self.env['product.product'].browse(vals['product_id'])
            if product.type == 'pbom':
                vals.update({
                    'qty': product.single_qty * vals['pcs'],
                    'pcs': vals['pcs'],
                })
            elif product.type == 'block':
                vals.update({
                    'qty': product.single_qty,
                    'pcs': 1,
                })
        return super(AbsComputeQty, self).create(vals)

    @api.multi
    def write(self, vals):
        if self.package_list_id:
            vals.update({'qty': self.package_list_id.qty, 'pcs': self.package_list_id.pcs})
        elif self.product_id:
            pcs = 1 if self.product_id.type == 'block' else vals.get('pcs') or self.pcs
            vals.update({'qty': self.product_id.single_qty * pcs, 'pcs': pcs})
        return super(AbsComputeQty, self).write(vals)

    @api.onchange('pcs')
    def onchange_qty(self):
        vals = {}
        if self.package_list_id:
            vals.update({'qty': self.package_list_id.qty, 'pcs': self.package_list_id.pcs})
        elif self.product_id:
            pcs = 1 if self.product_id.type == 'block' else self.pcs
            vals.update({'qty': self.product_id.single_qty * pcs, 'pcs': pcs})
        self.update(vals)


class PickingType(models.Model):
    _name = 'stock.picking.type'
    _description = '作业类型'

    name = fields.Char('作业名称', required=True)
    code = fields.Selection([('incoming', 'Vendors'), ('outgoing', 'Customers'), ('internal', 'Internal')],
                            'Type of Operation', required=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='仓库')

    default_location_src_id = fields.Many2one('stock.location', string='默认源库位置', store=True)
    default_location_dest_id = fields.Many2one('stock.location', string='默认目标库位置', store=True)

    is_production = fields.Boolean('生产作业', default=False)
    orig_product_type = fields.Selection(PRODUCT_TYPE_SELECTION, '原材料类型')
    product_type = fields.Selection(PRODUCT_TYPE_SELECTION, '成品类型')

    invoice_type_id = fields.Many2one('invoice.type', '账单类型')

    @api.onchange('code')
    def onchange_picking_code(self):
        if self.code == 'incoming':
            self.default_location_src_id = self.env.ref('project4.stock_location_suppliers').id
            self.default_location_dest_id = self.warehouse_id.lot_stock_id.id if self.warehouse_id else False
        elif self.code == 'outgoing':
            self.default_location_src_id = self.warehouse_id.lot_stock_id.id if self.warehouse_id else False
            self.default_location_dest_id = self.env.ref('project4.stock_location_customers').id

    @api.onchange('warehouse_id')
    def onchange_warehouse_id(self):
        if self.warehouse_id:
            if not self.code:
                return
            self.onchange_picking_code()


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
    move_ids = fields.One2many('stock.move', string='库存移动', compute='_compute_move_ids')
    state = fields.Selection(
        selection=(('draft', 'Draft'), ('waiting', 'Waiting'), ('confirm', 'Confirm'), ('done', 'Done')),
        string='Status', readonly=True, default='draft')
    order_line_ids = fields.One2many('stock.picking.line', 'picking_id', '作业明细行')
    order_line2_ids = fields.One2many('stock.picking.line2', 'picking_id', '作业明细行2')
    invoice_id = fields.One2many('invoice.order', 'picking_id', '账单')
    show_order_line2 = fields.Boolean('显示line2', compute='_compute_show_order_line2', store=True)

    block_ids = fields.Many2many('product.block', '荒料编号列表', compute='_compute_block_ids',
                                 help='用于产品order_line2_ids中可选的产品')

    @api.depends('order_line_ids.product_id.block_id')
    def _compute_block_ids(self):
        for record in self:
            record.block_ids = record.order_line_ids.mapped('product_id.block_id.id')

    @api.depends('order_line_ids.move_ids', 'order_line2_ids.move_ids')
    def _compute_move_ids(self):
        stock_move = self.env['stock.move']
        for record in self:
            stock_move |= record.order_line_ids.mapped('move_ids')
            stock_move |= record.order_line2_ids.mapped('move_ids')
            record.move_ids = stock_move

    @api.depends('picking_type_id.is_production', 'state')
    def _compute_show_order_line2(self):
        for record in self:
            if record.picking_type_id.is_production:
                if record.state != 'draft':
                    record.show_order_line2 = True
            else:
                record.show_order_line2 = False

    @api.onchange('picking_type_id', 'partner_id')
    def onchange_picking_type_id(self):
        if self.picking_type_id:
            self.default_location_src_id = self.picking_type_id.default_location_src_id.id
            self.default_location_dest_id = self.picking_type_id.default_location_dest_id.id

    @api.multi
    def _compute_state(self):
        for r in self:
            state_lst = r.move_ids.mapped('state')
            pass

    @api.multi
    def action_done(self):
        for record in self:
            record.move_ids._action_done()
            record._create_invoice()
        self.write({'state': 'done'})

    @api.multi
    def action_waiting(self):
        self.write({'state': 'waiting'})

    @api.multi
    def action_confirm(self):
        self.order_line_ids._action_confirm()
        self.order_line2_ids._action_confirm()
        self.write({'state': 'confirm'})

    def _prepare_invoice(self):
        return {
            'picking_id': self.id,
            'partner_id': self.partner_id.id,
            'invoice_type_id': self.picking_type_id.invoice_type_id.id,
            'currency_id': self.env.user.company_id.currency_id.id,
        }

    @api.multi
    def _create_invoice(self):
        for record in self:
            if record.picking_type_id.invoice_type_id:
                vals = record._prepare_invoice()
                invoice = self.env['invoice.order'].create(vals)
                record.order_line_ids._create_invoice_line(invoice)


class PickingLine(AbsComputeQty, models.Model):
    _name = 'stock.picking.line'
    _description = '作业单明细'

    sequence = fields.Integer('序号', default=10)
    picking_id = fields.Many2one('stock.picking', '作业单', required=True, readonly=True)
    product_id = fields.Many2one('product.product', string='产品')
    location_id = fields.Many2one('stock.location', string='库存位置', required=True)
    location_dest_id = fields.Many2one('stock.location', string='目标库位置')
    part = fields.Integer('夹数', related='package_list_id.part', store=True)
    # pcs = fields.Integer('件数', compute='_compute_qty', inverse='_set_pcs', store=True)
    pcs = fields.Integer('件数')
    reality_pcs = fields.Integer('实际件数')
    qty = fields.Float('数量', readonly=True, store=True)
    uom = fields.Many2one('product.uom', '单位', related='product_id.uom', readonly=True, store=True)
    package_list_id = fields.Many2one('package.list', '码单')
    unit_price = fields.Float('单价')
    amount = fields.Float('金额', compute='_compute_total')
    move_ids = fields.One2many('stock.move', 'picking_line_id', '库存移动', readonly=True)
    state = fields.Selection(
        selection=(('draft', 'Draft'), ('waiting', 'Waiting'), ('confirm', 'Confirm'), ('done', 'Done')),
        string='Status', readonly=True, default='draft', related='picking_id.state', store=True)
    purchase_line_id = fields.Many2one('purchase.order.line', '采购订单行', readonly=True)
    invoice_line_ids = fields.One2many('invoice.order.line', 'picking_line_id', '账单行')

    @api.depends('qty', 'unit_price')
    def _compute_total(self):
        for line in self:
            line.amount = line.qty * line.unit_price

    # @api.depends('product_id.type', 'reality_pcs', 'product_id.single_qty')
    # def _compute_qty(self):
    #     for r in self:
    #         if r.product_id.type == 'slab':
    #             r.qty = r.package_list_id.qty
    #             r.pcs = r.package_list_id.pcs
    #             r.part = r.package_list_id.part
    #         elif r.product_id.type == 'pbom':
    #             r.qty = r.product_id.single_qty * r.reality_pcs
    #             r.pcs = r.reality_pcs
    #         elif r.product_id.type == 'block':
    #             r.qty = r.product_id.single_qty
    #             r.pcs = 1

    def _get_qty(self, values):
        pcs = values.get('pcs')
        product = self.env['product.product'].browse(values['product_id']) if values.get('product_id') else None
        package_list = self.env['package.list'].browse(values['package_list_id']) if values.get(
            'package_list_id') else None
        if product:
            if product.type == 'pbom':
                return {
                    'qty': product.single_qty * pcs,
                    'pcs': pcs,
                }
            elif product.type == 'block':
                return {
                    'qty': product.single_qty,
                    'pcs': 1,
                }
        elif package_list:
            return {
                'qty': package_list.qty,
                'pcs': package_list.pcs,
            }
        return {}

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
            'pcs': self.pcs,
            'qty': self.qty,
        }

        if self.package_list_id:
            vals['slab_ids'] = self.package_list_id
        return vals

    @api.multi
    def _create_stock_move(self):
        move = self.move_ids[0] if self.move_ids else False
        vals = self._prepare_stock_move()
        if not move:
            move = self.env['stock.move'].create(vals)
        else:
            move.write(vals)

    @api.multi
    def _prepare_invoice_line(self, invoice):
        self.ensure_one()
        return {
            'product_id': self.product_id.id,
            'qty': self.qty,
            'uom': self.uom.id,
            'unit_price': self.unit_price,
            'currency_id': self.env.user.company_id.currency_id.id,
            'picking_line_id': self.id,
            'order_id': invoice.id,
        }

    @api.multi
    def _create_invoice_line(self, invoice):
        invoice_lines = invoice_line = self.env['invoice.order.line']
        for record in self:
            vals = record._prepare_invoice_line(invoice)
            invoice_lines |= invoice_line.create(vals)
        return invoice_lines

    @api.multi
    def _action_confirm(self):
        for record in self:
            record._create_stock_move()


class PickingLine2(models.Model):
    _name = 'stock.picking.line2'
    _inherit = 'stock.picking.line'

    block_id = fields.Many2one('product.block', '荒料编号')
    thickness_id = fields.Many2one('product.thickness', '厚度规格')

    @api.multi
    def _action_confirm(self):
        for record in self:
            record._create_product()
        return super(PickingLine2, self)._action_confirm()

    @api.multi
    def _prepare_product(self):
        return {
            'block_id': self.block_id.id,
            'thickness_id': self.thickness_id.id,
            'type': self.picking_id.picking_type_id.product_type
        }

    def _prepare_stock_move(self):
        self.ensure_one()
        vals = {
            'product_id': self.product_id.id,
            'location_id': self.location_id.id,
            'location_dest_id': self.location_dest_id.id,
            'picking_line2_id': self.id,
            'pcs': self.pcs,
            'qty': self.qty,
        }
        if self.package_list_id:
            vals['slab_ids'] = self.package_list_id
        return vals

    @api.multi
    def _create_product(self):
        for record in self:
            product = self.env['product.product'].search([('block_id', '=', record.block_id.id),
                                                          ('thickness_id', '=', record.thickness_id.id),
                                                          (
                                                              'type', '=',
                                                              record.picking_id.picking_type_id.product_type)])
            vals = record._prepare_product()
            if product:
                product.write(vals)
            else:
                product = self.env['product.product'].create(vals)
            record.product_id = product.id


class StockMove(AbsComputeQty, models.Model):
    _name = 'stock.move'
    _description = '库存移动作业'

    sequence = fields.Integer('序号', default=10)
    picking_line_id = fields.Many2one('stock.picking.line', '作业单明细行', required=True, readonly=True)
    picking_line2_id = fields.Many2one('stock.picking.line2', '作业单明细行2', required=True, readonly=True)
    picking_id = fields.Many2one('stock.picking', '作业单', related='picking_line_id.picking_id', store=True,
                                 readonly=True)
    orig_move_id = fields.Many2one('stock.move', string='源库存移动')
    location_id = fields.Many2one('stock.location', string='库存位置', readonly=True)
    location_dest_id = fields.Many2one('stock.location', string='目标库位置', readonly=True)
    product_id = fields.Many2one('product.product', string='产品', required=True)
    pcs = fields.Integer('件数', required=True)
    part = fields.Integer('夹数', related='package_list_id.part', store=True)
    qty = fields.Float('数量', required=True)
    uom = fields.Many2one('product.uom', '单位', related='product_id.uom', readonly=True, store=True)
    package_list_id = fields.Many2one('package.list', '码单')
    # slab_ids = fields.Many2many('product.slab', string='板材')
    state = fields.Selection(selection=(('draft', 'Draft'), ('confirm', 'Confirm'), ('done', 'Done')),
                             string='Status', readonly=True, default='draft')

    # @api.depends('slab_ids')
    # def _compute_part(self):
    #     for r in self:
    #         r.part = len(set(r.slab_ids.mapped('part_num')))



    @api.multi
    def _check_available_quant(self, out_moves):
        quant = self.env['stock.quant']
        for om in out_moves:
            available_pcs = quant._get_available(om.product_id, om.location_id)
            if om.pcs <= available_pcs:
                return True
            else:
                raise ValidationError('{}该产品的可以件数为:{}件,不够满足需求件数:{}件.不能够完成库存移动操作!'.format(om.product_id.name,
                                                                                         available_pcs, om.pcs))
    @api.multi
    def _action_confirm(self):
        quant = self.env['stock.quant']
        out_moves = self.env['stock.move']
        for move in self:
            out_moves |= move.filtered(lambda r: r.location_id.usage == 'internal')
        for om in out_moves:
            quant._update_reserved(om.product_id, om.location_id, om.pcs, om.package_list_id.slab_ids)
        self.write({'state': 'confirm'})

    @api.multi
    def _action_done(self):
        quant = self.env['stock.quant']
        out_moves = self.env['stock.move']
        in_moves = self.env['stock.move']
        for move in self:
            out_moves |= move.filtered(lambda r: r.location_id.usage == 'internal')
            in_moves |= move.filtered(lambda r: r.location_dest_id.usage == 'internal')
        self._check_available_quant(out_moves)
        for om in out_moves:
            quant._update_available(om.product_id, om.location_id, -om.pcs, om.package_list_id.slab_ids)
        for im in in_moves:
            quant._update_available(im.product_id, im.location_dest_id, im.pcs, im.package_list_id.slab_ids)
        self.write({'state': 'done'})
        return True


# class StockMoveLine(models.Model):
#     _name = 'stock.move.line'
#     _description = '库存移动作业明细'
#
#     move_id = fields.Many2one('stock.move', required=True, readonly=True)
#     location_id = fields.Many2one('stock.location', string='库存位置', readonly=True, required=True)
#     location_dest_id = fields.Many2one('stock.location', string='目标库位置', readonly=True, required=True)
#     pcs = fields.Integer('件数', required=True)
#     part = fields.Integer('夹数', related='package_list_id.part', store=True)
#     qty = fields.Float('数量', required=True)
#     uom = fields.Many2one('product.uom', '单位', related='product_id.uom', readonly=True, store=True)
#     package_list_id = fields.Many2one('package.list', '码单')