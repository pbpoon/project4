#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Created by pbpoon on 2018/2/6
from odoo import models, fields, api, exceptions


class Quant(models.Model):
    _name = 'stock.quant'
    _description = '库存框'
    _rec_name = 'product_id'

    product_id = fields.Many2one('product.product', '产品', ondelete='restrict', readonly=True, required=True)
    block_id = fields.Many2one('product.block', '荒料编号', related='product_id.block_id', store=True, readonly=True)
    location_id = fields.Many2one('stock.location', '库存位置', auto_join=True, ondelete='restrict', readonly=True,
                                  required=True)
    pcs = fields.Integer('件数')
    part = fields.Integer('夹数', compute='_compute_qty', store=True)
    qty = fields.Float('数量', required=True, readonly=True, compute='_compute_qty', store=True)
    uom = fields.Many2one('product.uom', '单位', related='product_id.uom', store=True, readonly=True)
    slab_ids = fields.One2many('product.slab', 'quant_id', string='板材')
    in_date = fields.Datetime('入库日期', readonly=True)

    _sql_constraints = [('unique_product_location', 'unique (product_id,location_id)', '该位置已有该产品,不能创建同位置同产品的库存框!')]

    @api.depends('product_id.type', 'slab_ids')
    def _compute_qty(self):
        for record in self:
            if record.product_id.type == 'slab':
                record.qty = sum(record.mapped('slab_ids.m2'))
                record.pcs = len(record.slab_ids)
                record.part = len(set(record.mapped('slab_ids.part_num')))
            elif record.product_id.type == 'pbom':
                record.qty = record.pcs * record.qty
                record.part = None
            elif record.product_id.type == 'block':
                record.qty = record.product_id.single_qty
                record.part = None

    @api.model
    def _get(self, product_id, location_id, strict=False):
        domain = [('product_id', '=', product_id.id)]
        if strict:
            domain.append(('location_id', '=', location_id.id))
        else:
            domain.append(('location_id', 'child_of', location_id.id))
        res = self.search(domain)
        return res

    @api.model
    def _update_available(self, product_id, location_id, pcs, slab_ids=None):
        self = self.sudo()
        if product_id.type == 'slab':
            if not slab_ids:
                raise exceptions.ValidationError('更新库存位置的板材产品没有附带码单!')
        quants = self._get(product_id, location_id, strict=True)
        for quant in quants:
            if (quant.pcs + pcs) < 0:
                raise exceptions.ValidationError('移出的库存数量不能大于库存数量!')
            vals = {'pcs': quant.pcs + pcs}
            if slab_ids:
                slabs = quants.slab_ids - slab_ids
                vals['slab_ids'] = [(6, 0, slabs.mapped('id'))]
            quant.write(vals)
            if quant.pcs == 0:
                quants.unlink()
            break
        else:
            if pcs <= 0:
                raise exceptions.ValidationError('对应新入库的数量不能为负数或零!')
            vals = {
                'product_id': product_id.id,
                'location_id': location_id.id,
                'pcs': pcs,
            }
            if product_id.type == 'slab':
                vals['slab_ids'] = [(6, 0, slab_ids.mapped('id'))]
            quant = self.create(vals)
        return quant
