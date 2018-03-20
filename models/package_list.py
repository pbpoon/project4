# -*- coding: utf-8 -*-

from odoo import models, fields, api


class PackageList(models.Model):
    _name = 'package.list'
    _description = '码单'

    name = fields.Char('码单明细', compute='_compute_total', store=True)
    product_id = fields.Many2one('product.product', '产品编号', required=True, index=True, ondelete='cascade')
    block_id = fields.Many2one('product.block', '荒料编号', related='product_id.block_id')
    qty = fields.Float('数量', compute='_compute_total', store=True, readonly=True)
    part = fields.Integer('夹数', compute='_compute_total', store=True, readonly=True)
    pcs = fields.Integer('件数', compute='_compute_total', store=True, readonly=True)
    slab_ids = fields.Many2many('product.slab', string='板材')

    @api.depends('slab_ids')
    def _compute_total(self):
        for record in self:
            qty = sum(record.mapped('slab_ids.m2'))
            part = len(set(record.mapped('slab_ids.part_num')))
            pcs = len(record.slab_ids)
            name = '{}/{}夹/{}件/{}m2'.format(record.product_id.name, part, pcs, qty)

            record.update({
                'qty': qty,
                'part': part,
                'pcs': pcs,
                'name': name,
            })

    @api.onchange('slab_ids')
    def _onchange_slab_ids(self):
        self.ensure_one()
        self.update({
            'qty': sum(self.slab_ids.mapped('m2')),
            'pcs': len(self.slab_ids),
            'part': len(set(self.slab_ids.mapped('part_num'))),
        })

    @api.multi
    def _get_res_model(self):
        res_model = self._context.get('res_model', False)
        res_id = self._context.get('res_id', False)
        if res_model and res_id:
            return self.env[res_model].browse(res_id)

        raise ValueError('错误的创建!')

    @api.model
    def create(self, vals):
        res = super(PackageList, self).create(vals)
        if self._context.get('res_model', False):
            self._get_res_model().write({'package_list_id': res.id})
        return res
