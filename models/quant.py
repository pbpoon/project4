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
    pcs = fields.Integer('件数', required=True, default=0)
    part = fields.Integer('夹数', compute='_compute_qty', store=True)
    qty = fields.Float('数量', compute='_compute_qty', store=True)
    uom = fields.Many2one('product.uom', '单位', related='product_id.uom', store=True, readonly=True)
    slab_ids = fields.One2many('product.slab', 'quant_id', string='板材')

    reserved_pcs = fields.Integer('预留件数')
    reserved_qty = fields.Float('预留数量', compute='_compute_qty', store=True)
    reserved_slab_ids = fields.Float('预留板材')

    in_date = fields.Datetime('入库日期', readonly=True)
    available_pcs = fields.Integer('可操作件数', compute='_compute_available_pcs', search='_available_pcs_search',
                                   store=True)

    _sql_constraints = [('unique_product_location', 'unique (product_id,location_id)', '该位置已有该产品,不能创建同位置同产品的库存框!')]

    def _available_pcs_search(self, name, args=None, operator='ilike', limit=100):
        if operator == 'like':
            operator = 'ilike'

        versions = self.search([('name', operator, name)], limit=limit)
        return versions.name_get()

    def _check_product_type(self, product_id, slab_ids=None):
        if product_id.type == 'slab' and slab_ids is None:
            raise exceptions.ValidationError('产品[ {} ]的形态为:板材,没有附带码单.不能对库存操作!')

    @api.depends('pcs', 'reserved_pcs')
    def _compute_available_pcs(self):
        for record in self:
            record.available_pcs = record.pcs - record.reserved_pcs

    @api.depends('product_id.type', 'slab_ids')
    def _compute_qty(self):
        for record in self:
            if record.product_id.type == 'slab':
                record.qty = sum(record.mapped('slab_ids.m2'))
                record.pcs = len(record.slab_ids)
                record.part = len(set(record.mapped('slab_ids.part_num')))
                record.reserved_qty = sum(record.mapped('reserved_slab_ids.m2'))
            elif record.product_id.type == 'pbom':
                record.qty = record.pcs * record.product_id.single_qty
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
    def _update_reserved(self, product_id, location_id, pcs, slab_ids, strict=False):
        """
        :param product_id:
        :param location_id:
        :param pcs:
        :param slab_ids:
        :param strict:
        :return: tuple(quant(recordset), pcs(int), slab_ids(list))
        """
        self._check_product_type(product_id, slab_ids)
        quants = self._get(product_id, location_id, strict=strict)
        # available = self._get_available(product_id, location_id)
        reserved_quants = []
        if slab_ids:
            quantity = len(slab_ids.mapped('id')) * -1 if pcs < 0 else len(slab_ids.mapped('id'))
        else:
            quantity = pcs
        for quant in quants:
            if quantity > 0:
                max_reserved_pcs = quant.pcs - int(quant.reserved_pcs)
                if max_reserved_pcs <= 0:
                    continue
                reserved_slab_ids = []
                if slab_ids:
                    quant.reserved_slab_ids = slab_ids & quant.slab_ids
                    slab_ids -= quant.reserved_slab_ids
                    reserved_slab_ids = quant.mapped('reserved_slab_ids.id')
                max_reserved_pcs = min(max_reserved_pcs, quantity)
                quant.reserved_pcs += max_reserved_pcs
                reserved_quants.append((quant, max_reserved_pcs, reserved_slab_ids))
                quantity -= max_reserved_pcs
            else:
                max_reserved_pcs = min(quant.reserved_pcs, abs(quantity))
                reserved_slab_ids = []
                if slab_ids:
                    reserved_slab_ids = quant.mapped('reserved_slab_ids.id')
                    quant.reserved_slab_ids -= slab_ids
                    slab_ids -= quant.reserved_slab_ids
                quant.reserved_pcs -= max_reserved_pcs
                reserved_quants.append((quant, -quantity, reserved_slab_ids))
                quantity += max_reserved_pcs
            if quantity == 0:
                break
        return reserved_quants

    @api.model
    def _get_available(self, product_id, location_id):
        """
        :param product_id:(record)
        :param location_id: location(record)
        :return: tuple(pcs(int), slabs(list))
        """
        quants = self._get(product_id, location_id)
        slabs = [quant.mapped('slab_ids.id') for quant in quants]
        pcs = sum(quant.pcs for quant in quants)
        return pcs, slabs

    @api.model
    def _update_available(self, product_id, location_id, pcs, slab_ids=None):
        self._check_product_type(product_id, slab_ids)
        self = self.sudo()
        if product_id.type == 'slab':
            if not slab_ids:
                raise exceptions.ValidationError('更新库存位置的板材产品没有附带码单!')
        quants = self._get(product_id, location_id, strict=True)
        balance = 0
        for quant in quants:
            # if (quant.pcs + pcs) < 0:
            #     raise exceptions.ValidationError('移出的库存数量不能大于库存数量!')
            balance += quant.pcs + pcs
            vals = {'pcs': quant.pcs + pcs}
            if slab_ids:
                slabs = quants.slab_ids - slab_ids
                vals['slab_ids'] = [(6, 0, slabs.mapped('id'))]
            quant.write(vals)
            if quant.pcs == 0 and quant.reserved_pcs == 0:
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
