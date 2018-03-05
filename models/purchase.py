#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Created by pbpoon on 2018/2/27

from odoo import fields, api, models, _

COST_MONEY_SELECTION = (
    ('USD', u'$美元'),
    ('CNY', u'￥人民币'),
    ('EUR', u'€欧元'),
)
COST_BY_SELECTION = (
    ('weight', '按重量'),
    ('m3', '按立方'),
)


class PurchaseOrder(models.Model):
    _name = 'purchase.order'
    _description = '采购订单'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    @api.multi
    def _compute_picking(self):
        pickings = self.env['stock.picking']
        for order in self:
            for line in order.order_line_ids:
                moves = line.mapped('move_ids')
                pickings |= moves.mapped('picking_id')
            order.picking_ids = pickings

    name = fields.Char('code', required=True, readonly=True, index=True, default=lambda self: _('New'))
    date = fields.Date('采购日期', required=True)
    state = fields.Selection((('draft', 'Draft'), ('confirm', 'Confirm'), ('done', 'Done')), 'Status', readonly=True,
                             default='draft', index=True, track_visibility='onchange')
    order_line_ids = fields.One2many('purchase.order.line', 'order_id', string='明细行')
    partner_id = fields.Many2one('res.partner', '供应商', required=True)  # 后面设置domain

    handler_id = fields.Many2one('res.partner', '经办人', default=lambda self: self.env.user)
    cost_money = fields.Selection(selection=COST_MONEY_SELECTION, string='结算货币',
                                  default='USD')
    # quarry_id = fields.Many2one('product.quarry', '矿口')
    # batch_id = fields.Many2one('product.batch', '批次')
    # category_id = fields.Many2one('product.category', '品种分类', required=True, )
    # cost_by = fields.Selection(selection=COST_BY_SELECTION, string='成本计算方式', default='weight')
    currency_id = fields.Many2one("res.currency", string="Currency", required=True)

    product_block_import_order_id = fields.Many2one('product.block.import.order', '导入荒料明细')
    total_amount = fields.Float('总金额', digits=(5, 2), compute='_compute_total')
    total_count = fields.Integer('个数', compute='_compute_total')
    total_qty = fields.Float('总重量', digits=(5, 2), compute='_compute_total')
    picking_ids = fields.Many2many('stock.picking', string='库存作业单', compute='_compute_picking', copy=False, store=True)
    picking_type_id = fields.Many2one('stock.picking.type', '作业类型', required=True)

    @api.multi
    def _compute_total(self):
        for record in self:
            record.total_count = len(record.order_line_ids)
            record.total_qty = sum(record.mapped('order_line_ids.qty'))
            record.total_amount = sum(record.mapped('order_line_ids.amount'))

    @api.onchange('product_block_import_order_id')
    def onchange_import_product_line_id(self):
        if not self.product_block_import_order_id:
            return {}
        new_lines = self.env['purchase.order.line']
        for line in self.product_block_import_order_id.order_line_ids:
            data = {'product_id': line.product_id.id,
                    'unit_price': line.unit_price}
            new_line = new_lines.new(data)
            new_lines += new_line
        self.order_line_ids += new_lines
        self.product_block_import_order_id = False
        for line in self.order_line_ids:
            line._onchange_product_id()
        return {}

    @api.multi
    def action_confirm(self):
        self.ensure_one()
        self._create_picking()
        self.write({'state': 'confirm'})

    @api.multi
    def action_draft(self):
        self.ensure_one()
        self.write({'state': 'draft'})

    def _prepare_picking(self):
        return {
            'picking_type_id': self.env['stock.picking.type'].search([])[0].id,  # 日后需要改
            'partner_id': self.partner_id.id,
        }

    @api.multi
    def _create_picking(self):
        StockPicking = self.env['stock.picking']
        for record in self:
            pickings = record.picking_ids.filtered(lambda r: r.state not in ('done', 'cancel'))
            if not pickings:
                picking = StockPicking.create(self._prepare_picking())
            else:
                picking = pickings[0]
            moves = record.order_line_ids._create_picking_line(picking)
        return True


class PurchaseOrderLine(models.Model):
    _name = 'purchase.order.line'
    _description = '采购单明细行'

    name = fields.Char('说明')
    order_id = fields.Many2one('purchase.order', '采购订单', required=True, readonly=True, ondelete='cascade')
    sequence = fields.Integer('序号', default=10)
    # category_id = fields.Many2one('product.category', '品种分类', required=True, )
    # quarry_id = fields.Many2one('product.quarry', '矿口', required=True, )
    # batch_id = fields.Many2one('product.batch', '批次', required=True, )
    product_id = fields.Many2one('product.product', '产品', required=True, domain=[('type', '=', 'block')])
    pcs = fields.Integer('件数', default=1)
    qty = fields.Float('数量', related='product_id.single_qty', store=True)
    uom = fields.Many2one('product.uom', '单位', related='product_id.uom', readonly=True)
    unit_price = fields.Float('单价')
    amount = fields.Float('金额', compute='_compute_amount')
    cost_money = fields.Selection(selection=COST_MONEY_SELECTION, string='结算货币',
                                  default='USD', related='order_id.cost_money')
    # cost_by = fields.Selection(selection=COST_BY_SELECTION, string='成本计算方式', default='weight')
    state = fields.Selection((('draft', 'Draft'), ('confirm', 'Confirm'), ('done', 'Done')), 'Status', readonly=True,
                             default='draft', index=True, related='order_id.state')
    picking_line_ids = fields.One2many('stock.picking.line', 'purchase_line_id', '作业单明细行')
    # move_ids = fields.One2many('stock.move', 'purchase_line_id', '库存移动')

    @api.depends('qty', 'unit_price')
    def _compute_amount(self):
        for r in self:
            r.amount = r.qty * r.unit_price

    @api.onchange('product_id')
    def _onchange_product_id(self):
        self.amount = self.qty * self.unit_price

    @api.multi
    def _prepare_picking_line(self, picking):
        self.ensure_one()
        vals = {
            'purchase_id': self.order_id.id,
            'product_id': self.product_id.id,
            'pcs': self.pcs,
            'qty': self.qty,
            'uom': self.uom,
            'picking_id': picking.id,
            'location_id': self.env['stock.location'].search([])[0].id
        }
        return vals

    @api.multi
    def _create_picking_line(self, picking):
        picking_line = self.env['stock.picking.line']
        done = self.env['stock.picking.line'].browse()
        for line in self:
            vals = line._prepare_picking_line(picking)
            done += picking_line.create(vals)
        return done
