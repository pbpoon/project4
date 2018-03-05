#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Created by pbpoon on 2018/1/9

from odoo import models, api, fields, _, exceptions
import odoo.addons.decimal_precision as dp
from odoo.exceptions import ValidationError, RedirectWarning, except_orm

COST_BY_SELECTION = (
    ('weight', '按重量'),
    ('m3', '按立方'),
    ('m2', '按平方'),
)
QTY_UOM_SELECTION = [
    ('t', 't'),
    ('m2', 'm2'),
    ('m3', 'm3')
]


class ProductBlockImportOrder(models.Model):
    _name = 'product.block.import.order'

    # def _get_default_category_id(self):
    #     if self._context.get('categ_id') or self._context.get('default_categ_id'):
    #         return self._context.get('categ_id') or self._context.get('default_categ_id')
    #     category = self.env.ref('product.product_category_all', raise_if_not_found=False)
    #     if not category:
    #         category = self.env['product.category'].search([], limit=1)
    #     if category:
    #         return category.id
    #     else:
    #         err_msg = _('You must define at least one product category in order to be able to create products.')
    #         redir_msg = _('Go to Internal Categories')
    #         raise RedirectWarning(err_msg, self.env.ref('product.product_category_action_form').id, redir_msg)

    # def _get_quarry_selection(self):
    #     selection = [(name, name) for name in self.env['product.quarry'].search([]).mapped('name')]
    #     return selection
    #
    # def _get_batch_selection(self):
    #     selection = [(name, name) for name in self.env['product.batch'].search([]).mapped('name')]
    #     return selection

    name = fields.Char('采购订单号', readonly=True, store=True, index=True, default=lambda self: _('New'))
    date = fields.Date('采购日期', required=True)
    cost_by = fields.Selection(selection=COST_BY_SELECTION, string='成本计算方式', default='weight')
    order_line_ids = fields.One2many('product.block.import.order.line', 'order_id', string='订单明细')
    category_id = fields.Many2one(
        'product.category', '品种分类',
        change_default=True, help="Select category for the current product")
    quarry_id = fields.Many2one('product.quarry', '矿口')
    batch_id = fields.Many2one('product.batch', '批次')
    product_id = fields.Many2one('product.product', '产品')
    total_count = fields.Integer('个数', compute='_compute_total')
    total_weight = fields.Float('总重量', digits=(5, 2), compute='_compute_total')

    state = fields.Selection([
        ('draft', _('Draft')),
        ('confirm', _('Confirm')),
        ('done', _('Done')),
    ], string='Status', readonly=True, copy=False, index=True, track_visibility='onchange', default='draft')

    @api.multi
    def action_confirm(self):
        for record in self:
            record.state = 'confirm'
            record.confirmation_date = fields.Datetime.now()
            record.order_line_ids.action_confirm()
            return True

    @api.multi
    def action_cancel(self):
        self.ensure_one()
        self.write({'state': 'cancel', 'confirmation_date': False})
        self.order_line_ids.action_cancel()

    @api.multi
    def action_done(self):
        self.write({'state': 'done'})
        return self.order_line_ids.write({'state': 'done'})

    @api.depends('state')
    def _onchange_state(self):
        self.order_line_ids.state = self.state

    @api.multi
    def action_draft(self):
        self.write({'state': 'draft'})
        return self.order_line_ids.action_draft()

    @api.multi
    def _compute_total(self):
        for record in self:
            record.total_count = len([line for line in record.order_line_ids])
            record.total_weight = sum(line.weight for line in record.order_line_ids)

    def action_create_purchase_order(self):
        self.ensure_one()
        order_line = []
        for line in self.mapped('order_line_ids'):
            order_line.append([0, False, {
                'product_id': line.product_id.id,
                'qty': line.product_id.qty,
                'qty_uom': line.product_id.qty_uom,
                'price_unit': line.unit_price,
            }])
        partner_id = self.env['res.partner'].search([('name', '=', 'kkk')]).id
        context = self.env.context.copy()
        context.update(
            {'default_state': 'done', 'default_partner_id': partner_id, 'default_order_line': order_line},
        )
        # self.with_context(default_order_line=order_line_ids)
        action = self.env.ref('purchase.purchase_rfq')
        return {
            'type': action.type,
            'res_model': action.res_model,
            # 'view_id': action.view_id,
            'views': [[False, 'form']],
            'context': context,
        }


class ProductBlockImportOrderLine(models.Model):
    _name = 'product.block.import.order.line'
    _inherits = {'product.block': 'block_id'}

    # name = fields.Char('编号', required=True, index=True)
    # quarry_id = fields.Many2one('product.quarry', '矿口')
    # batch_id = fields.Many2one('product.batch', '批次')
    # category_id = fields.Many2one(
    #     'product.category', '品种分类',
    #     change_default=True, help="Select category for the current product")
    # # ------------荒料数据--------------------
    # weight = fields.Float('重量', digits=(3, 2), help='单位为:t')
    # m3 = fields.Float('立方', digits=(3, 2), store=True)
    # long = fields.Integer('长', help='单位为:cm')
    # width = fields.Integer('宽', help='单位为:cm')
    # height = fields.Integer('高', help='单位为:cm')
    sequence = fields.Integer('序号', default=10)
    product_id = fields.Many2one('product.product', '产品')
    order_id = fields.Many2one('product.block.import.order', 'order', ondelete='cascade', required=True)

    unit_price = fields.Float('单价')

    def _prepare_product_value(self, block):
        return {
            'block_id': block.id,
            'type': 'block'
        }

    @api.onchange('long', 'width', 'height', 'weight')
    def _onchange_m3(self):
        for r in self:
            if not r.cost_by:
                return None
            if r.cost_by == 'm3':
                if r.long and r.width and r.height:
                    r.m3 = r.long * r.width * r.height * 0.00001
                else:
                    r.m3 = None
            else:
                r.m3 = r.weight / 2.8

    @api.model
    def create(self, vals):
        order = self.order_id.browse(vals.get('order_id'))

        if not vals.get('category_id'):
            if not order.category_id:
                raise exceptions.ValidationError('请选择品种名称!')
            vals.update({'category_id': order.category_id.id})

        if not vals.get('quarry_id'):
            if not order.quarry_id:
                raise exceptions.ValidationError('请选择矿口名称!')
            vals.update({'quarry_id': order.quarry_id.id})

        if not vals.get('batch_id'):
            if not order.batch_id:
                raise exceptions.ValidationError('请选择批次名称!')
            vals.update({'batch_id': order.batch_id.id})

        res = super(ProductBlockImportOrderLine, self).create(vals)

        product_value = self._prepare_product_value(res.block_id)
        product = self.env['product.product'].create(product_value)
        res.write({'product_id': product.id})

        return res
