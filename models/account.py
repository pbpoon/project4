#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Created by pbpoon on 2018/2/6
from odoo import models, fields, api, _
from odoo.exceptions import UserError

INVOICE_STATE = (
    ('draft', '草稿'), ('confirm', '确认'), ('done', '完成'), ('cancel', '关闭')
)


class InvoiceType(models.Model):
    _name = 'invoice.type'
    _description = '款项类型'

    name = fields.Char('类型名称')
    code = fields.Selection((('collection', '收款'), ('payment', '付款')), '款项类型', required=True, index=True)


class InvoiceOrder(models.Model):
    _name = 'invoice.order'
    _description = '账单'

    name = fields.Char('名称', required=True, index=True, default=lambda self: _('New'))
    partner_id = fields.Many2one('res.partner', '对方', required=True)
    invoice_type_id = fields.Many2one('invoice.type', '款项名称', required=True)
    code = fields.Selection((('collection', '收款'), ('payment', '付款')), '款项类型', related='invoice_type_id.code',
                            store=True)
    finish = fields.Boolean('完成', default=False)
    order_line_ids = fields.One2many('invoice.order.line', 'order_id', '账单明细行')
    currency_id = fields.Many2one("res.currency", string="Currency", required=True)
    date_due = fields.Date('支付限期')
    state = fields.Selection(INVOICE_STATE, '状态', compute='_compute_state', store=True)
    amount = fields.Float('金额', compute='_compute_amount', store=True)
    amount_due = fields.Float('未付金额', compute='_compute_amount', store=True)
    payment_ids = fields.One2many('invoice.payment', 'invoice_id', '付款记录')
    picking_id = fields.Many2one('stock.picking', '作业单')
    sales_order_id = fields.Many2one('sales.order', '销售单')

    @api.depends('order_line_ids.amount')
    def _compute_amount(self):
        for record in self:
            record.amount = sum(record.mapped('order_line_ids.amount'))

    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('invoice.order') or _('New')
        return super(InvoiceOrder, self).create(vals)


class InvoiceOrderLine(models.Model):
    _name = 'invoice.order.line'
    _description = '账单明细行'

    name = fields.Char('项目说明', compute='_compute_name', inverse='_set_name', store=True)
    sequence = fields.Integer('序号', default=10)
    desc = fields.Char('摘要')
    order_id = fields.Many2one('invoice.order', '账单', required=True, readonly=True)
    product_id = fields.Many2one('product.product', '产品')
    qty = fields.Float('数量', required=True)
    uom = fields.Many2one('product.uom', '单位')
    unit_price = fields.Float('单价', required=True)
    currency_id = fields.Many2one("res.currency", string="Currency", required=True,
                                  default=lambda self: self.user.company_id.currency_id.id)
    amount = fields.Float('金额', compute='_compute_amount', inverse='_set_amount')
    picking_line_id = fields.Many2one('stock.picking.line', '作业单明细行', readonly=True)
    sales_line_id = fields.Many2one('sales.order.line', '销售订单明细行', readonly=True)

    @api.depends('desc', 'product_id')
    def _compute_name(self):
        for record in self:
            name = "{} ".format(record.product_id.name) if record.product_id else ""
            desc = record.desc if record.desc else ""
            record.name = name + desc

    def _set_name(self):
        self.desc = self.name

    @api.depends('qty', 'unit_price')
    def _compute_amount(self):
        for record in self:
            record.amount = record.unit_price * record.qty

    @api.multi
    def _set_amount(self):
        self.unit_price = self.amount / self.qty


class InvoicePayment(models.Model):
    _name = 'invoice.payment'
    _description = '付款记录'

    invoice_id = fields.Many2one('invoice.order', '账单', required=True, readonly=True)
    amount = fields.Float('金额', required=True)

# class BankAccount(models.Model):
#     _name = 'bank.account'
#     _description = '银行账号'
#
#     name = fields.Char('名称', required=True, index=True)
