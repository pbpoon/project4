#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Created by pbpoon on 2018/2/27

from odoo import fields, api, models, _, exceptions
from .stock import AbsComputeQty


class SalesOrder(models.Model):
    _name = 'sales.order'
    _description = '销售订单'

    def _get_default_warehouse_id(self):
        return self.env.ref('project4.stock_location_locations').id

    def _get_default_picking_type_id(self):
        type_id = self.env['stock.picking.type'].search(
            [('code', '=', 'outgoing'), ('warehouse_id.company_id', '=', self.env.user.company_id.id)])
        if not type_id:
            self.env['stock.picking.type'].search([('code', '=', 'outgoing')])
        # if not type_id:
        #     raise exceptions.UserError('你公司没有设置提货作业,请设置完成后才能通过审查!')
        return type_id[:1]

    name = fields.Char('订单号', default=lambda self: _('New'), readonly=True, index=True)
    partner_id = fields.Many2one('res.partner', string='客户', required=True)
    date = fields.Datetime('日期', default=fields.Datetime.now, required=True)
    sale_man = fields.Many2one('res.users', '业务代表')
    order_line_ids = fields.One2many('sales.order.line', 'order_id', '明细行')
    state = fields.Selection((('draft', 'Draft'), ('confirm', 'Confirm'), ('done', 'Done')), 'Status', readonly=True,
                             default='draft', index=True, track_visibility='onchange')
    warehouse_id = fields.Many2one('stock.warehouse', '交货仓库', required=True, default=_get_default_warehouse_id)
    # address = fields.Char('销往区域', compute='_compute_address', store=True)
    # state_id = fields.Many2one("res.country.state", string='省份', ondelete='restrict', required=True)
    # city_id = fields.Many2one('area.city', '城市', required=True)
    # district_id = fields.Many2one('area.district', '市县/行政区', required=True)
    picking_ids = fields.One2many('stock.picking', string='提货作业单号', compute='_compute_picking_ids')
    picking_type_id = fields.Many2one('stock.picking.type', string='作业类型', required=True,
                                      defaulte=_get_default_picking_type_id)
    amount_total = fields.Float('总金额', compute='_compute_total', store=True)
    picking_count = fields.Integer('提货记录数', compute='_compute_picking_count')
    invoice_ids = fields.One2many('invoice.order', string='账单', compute='_compute_invoice')
    delivery_progress = fields.Float('提货进度', compute='_compute_delivery')

    @api.depends('order_line_ids')
    def _compute_delivery(self):
        for record in self:
            all_qty = sum(record.order_line_ids.mapped('qty'))
            all_delivery_qty = sum(record.order_line_ids.mapped('delivery_qty'))
            record.delivery_progress = all_delivery_qty / all_qty * 100 if all_qty > 0 else False

    @api.depends('order_line_ids')
    def _compute_invoice(self):
        invoice_orders = self.env['invoice.order']
        for record in self:
            invoice_orders |= record.order_line_ids.mapped('invoice_line_ids').filtered(lambda r: r.state != 'cancel')
            record.invoice_ids = invoice_orders

    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('sales.order')
        return super(SalesOrder, self).create(vals)

    @api.depends('order_line_ids.amount')
    def _compute_total(self):
        for record in self:
            record.amount_total = sum(record.order_line_ids.mapped('amount'))

    @api.multi
    def _compute_picking_count(self):
        for record in self:
            record.picking_count = len(record.picking_ids)

    @api.depends('order_line_ids.picking_line_ids')
    def _compute_picking_ids(self):
        pickings = self.env['stock.picking']
        for record in self:
            for line in record.order_line_ids:
                pickings |= line.mapped('picking_line_ids.picking_id')
            record.picking_ids = pickings

    @api.depends('state_id', 'city_id', 'district_id')
    def _compute_address(self):
        for record in self:
            name = '{}/{}/{}'.format(record.state_id.name, record.city_id.name, record.district_id.name)
            record.address = name

    def _prepare_picking(self):
        return {
            'picking_type_id': self.picking_type_id.id,
            'partner_id': self.partner_id.id,
            'warehouse_id': self.warehouse_id.id,
            'date': self.date,
            # 日后可添加提货日期
        }

    @api.multi
    def _create_picking(self):
        for record in self:
            pickings = record.picking_ids.filtered(lambda r: r.state not in ('done', 'cancel'))
            if not pickings:
                vals = record._prepare_picking()
                picking = self.env['stock.picking'].create(vals)
            else:
                picking = pickings[0]
            record.order_line_ids._create_picking_line(picking)
            picking.action_confirm()
        return True

    def _prepare_invoice(self):
        return {
            'partner_id': self.partner_id.id,
            'invoice_type_id': self.partner_id.id,
            'warehouse_id': self.warehouse_id.id,
            'date': self.date,
            # 日后可添加提货日期
        }

    @api.multi
    def _create_invoice(self):
        for record in self:
            invoices = record.invoice_ids
            if not invoices:
                vals = record._prepare_invoice()
                invoice = self.env['stock.picking'].create(vals)
            else:
                invoice = invoices[0]
            record.order_line_ids._create_invoice_line(invoice)
            invoice.action_confirm()
        return True

    @api.multi
    def action_confirm(self):
        self._create_picking()
        self.write({'state': 'confirm'})

    @api.multi
    def action_view_picking(self):
        pickings = self.mapped('picking_ids')
        action = self.env.ref('project4.picking_action_window').read()[0]
        if len(pickings) > 1:
            action['domain'] = [('id', 'in', pickings.ids)]
        elif len(pickings) == 1:
            action['views'] = [(False, 'form')]
            action['res_id'] = pickings.ids[0]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action


class SalesOrderLine(AbsComputeQty, models.Model):
    _name = 'sales.order.line'
    _description = '销售订单明细行'

    name = fields.Char('产品项目', compute='_compute_name', store=True)
    order_id = fields.Many2one('sales.order', '销售订单', required=True, readonly=True, ondelete='cascade')
    sequence = fields.Integer('序号', default=10)
    product_id = fields.Many2one('product.product', '产品', required=True)

    # part = fields.Integer('夹数', related='package_list_id.part', store=True)
    # pcs = fields.Integer('件数', compute='_compute_qty', inverse='_set_pcs', store=True)
    # pbom_pcs = fields.Integer('件数')
    # qty = fields.Float('数量', compute='_compute_qty', store=True)
    # uom = fields.Many2one('product.uom', '单位', related='product_id.uom', store=True)
    # package_list_id = fields.Many2one('package.list', string='码单')

    unit_price = fields.Float('单价')
    amount = fields.Float('金额', compute='_compute_amount')
    warehouse_id = fields.Many2one('stock.warehouse', '交货仓库', required=True)
    # cost_money = fields.Selection(selection=COST_MONEY_SELECTION, string='结算货币',
    #                               default='USD', related='order_id.cost_money')
    # cost_by = fields.Selection(selection=COST_BY_SELECTION, string='成本计算方式', default='weight')
    state = fields.Selection((('draft', 'Draft'), ('confirm', 'Confirm'), ('done', 'Done')), 'Status', readonly=True,
                             default='draft', index=True, related='order_id.state')
    picking_line_ids = fields.One2many('stock.picking.line', 'sales_line_id', string='提货作业明细行')
    invoice_line_ids = fields.One2many('invoice.order.line', 'sales_line_id', string='账单明细行')
    delivery_pcs = fields.Integer('提货件数', compute='_compute_delivery', store=True)
    delivery_qty = fields.Float('提货数量', compute='_compute_delivery', store=True)
    on_stock_qty = fields.Float('可提货数量', compute='_compute_delivery', store=True)
    on_stock_pcs = fields.Integer('可提货件量', compute='_compute_delivery', store=True)
    on_stock_slab_ids = fields.One2many('product.slab', string='可提货板材', compute='_compute_on_stock_slab_ids')

    @api.depends('picking_line_ids')
    def _compute_on_stock_slab_ids(self):
        slabs = self.env['product.slab']
        for record in self:
            slabs |= record.package_list_id.mapped('slab_ids')
            slabs -= record.picking_line_ids.filtered(lambda r: r.state == 'done').mapped('package_list_id.slab_ids')
            record.on_stock_slab_ids = slabs

    @api.depends('picking_line_ids.state', 'picking_line_ids.pcs')
    def _compute_delivery(self):
        for record in self:
            if self.state not in ('draft', 'cancel'):
                done_picking_lines = record.picking_line_ids.filtered(lambda r: r.state == 'done')
                record.delivery_pcs = sum(done_picking_lines.mapped('pcs'))
                record.delivery_qty = sum(done_picking_lines.mapped('qty'))
                record.on_stock_pcs = record.pcs - record.delivery_pcs
                record.on_stock_qty = record.qty - record.delivery_qty


    @api.depends('unit_price', 'qty')
    def _compute_amount(self):
        for record in self:
            record.amount = record.unit_price * record.qty

    @api.depends('product_id.name', 'part', 'pcs', 'qty', 'uom')
    def _compute_name(self):
        for record in self:
            detail = "{}夹/{}件/{}{}".format(record.part, record.pcs, record.qty,
                                           record.uom) if record.product_id.type == 'slab' else \
                "{}{}".format(record.qty, record.uom)
            record.name = '{}/{}'.format(record.product_id.name, detail)

    @api.onchange('warehouse_id')
    def onchange_warehouse_id(self):
        if self.warehouse_id:
            product_lst = self.warehouse_id.lot_stock_id.get_available_product_lst()
            product_lst = [product.id for product in self.env['product.product'].browse(product_lst) if
                           product.type != 'pbom']
            return {'domain': {'product_id': [('id', 'in', product_lst)]}}

    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            quant = self.env['stock.quant']._get_available(self.product_id, self.warehouse_id.lot_stock_id)

    def _prepare_picking_line(self, picking):
        self.ensure_one()
        vals = {
            'product_id': self.product_id.id,
            'pcs': self.pcs,
            'qty': self.qty,
            'sales_line_id': self.id,
            'picking_id': picking.id,
            'location_id': self.warehouse_id.lot_stock_id.id,
            'location_dest_id': self.env.ref('project4.stock_location_customers').id,
        }
        if self.package_list_id:
            vals['package_list_id'] = self.package_list_id.copy().id,
        return vals

    @api.multi
    def _create_picking_line(self, picking):
        for record in self:
            picking_lines = record.mapped('picking_line_ids').filtered(lambda r: r.state not in ('done', 'cancel'))
            vals = record._prepare_picking_line(picking)
            if picking_lines:
                return picking_lines[0].write(vals)
            return self.env['stock.picking.line'].create(vals)

    def _prepare_invoice_line(self, invoice):
        self.ensure_one()
        vals = {
            'product_id': self.product_id.id,
            'pcs': self.pcs,
            'qty': self.qty,
            'uom': self.uom,
            'sales_line_id': self.id,
            'order_id': invoice.id,
            'unit_price': self.unit_price,
        }
        if self.package_list_id:
            vals['package_list_id'] = self.package_list_id.copy().id,
        return vals

    @api.multi
    def _create_invoice_line(self, invoice):
        for record in self:
            picking_lines = record.mapped('picking_line_ids').filtered(lambda r: r.state not in ('done', 'cancel'))
            vals = record._prepare_invoice_line(invoice)
            if picking_lines:
                return picking_lines[0].write(vals)
            return self.env['stock.picking.line'].create(vals)

    @api.multi
    def action_show_package_list(self):
        self.ensure_one()
        if self.product_id:
            if self.product_id.type != 'slab':
                return {}
        ctx = self.env.context.copy()
        res_id = self.package_list_id.id if self.package_list_id else False
        name = '码单' if self.package_list_id else '新建码单'
        quant = self.env['stock.quant']._get_available(self.product_id, self.warehouse_id.lot_stock_id)

        ctx.update({
            'res_model': self._name,
            'res_id': self.id,
            'default_product_id': self.product_id.id,
        })
        ctx['domain_slab_ids'] = quant[1]
        return {
            'name': name,
            'res_model': 'package.list',
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_id': res_id,
            'context': ctx,
        }
