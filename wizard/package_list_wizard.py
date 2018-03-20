#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Created by pbpoon on 2018/1/25

from odoo import api, models, fields
import xlrd
import base64
import io


class PackageList(models.TransientModel):
    _name = 'package.list.wizard'

    product_id = fields.Many2one('product.product', '产品', readonly=True)
    from_num = fields.Integer('从', required=True, default=1)
    to_num = fields.Integer('到')
    part_num = fields.Integer('夹号', required=True, default=1)

    part = fields.Integer('夹数')
    pcs = fields.Integer('件数')
    qty = fields.Integer('数量')

    file = fields.Binary('文件')

    long = fields.Integer('长')
    height = fields.Integer('高')
    kl1 = fields.Integer('扣迟长')
    kh1 = fields.Integer('扣迟高')
    kl2 = fields.Integer('扣迟2长')
    kh2 = fields.Integer('扣迟2高')

    slab_ids = fields.Many2many('product.slab.wizard', string='板材规格')

    def import_file(self):
        """导入excel文件
        :return:
        """
        f = io.BytesIO(base64.b64encode(self.file))
        file = xlrd.open_workbook(f)
        table = file.sheets()[0]
        nrows = table.nrows  # 总行数
        colnames = table.row_values(0)  # 表头列名称数据
        print(colnames)
        lst = []
        for rownum in range(1, nrows):
            rows = table.row_values(rownum)
            item = {}
            for colname, row in zip(colnames, rows):
                item[colname] = row
                lst.append(item)
        print(lst)
        self._open_view()

    def Apply(self):
        slab_lst = []
        # location_id = self._context.get('location_id')

        for record in self.slab_ids:
            data = {
                'product_id': record.product_id.id,
                'sequence': record.sequence,
                'part_num': record.part_num,
                'long': record.long,
                'height': record.height,
                'kl1': record.kl1,
                'kh1': record.kh1,
                'kl2': record.kl2,
                'kh2': record.kh2,
            }
            slab = self.env['product.slab'].create(data)
            slab_lst.append(slab.id)
        package_list = self.env['package.list'].create({
            'product_id': self.product_id.id, 'slab_ids': [(6, 0, slab_lst)]
        })

        # self._res_model().write({'package_list_id': package_list.id})

    def button_add(self):
        self.ensure_one()
        new_slab_ids = self.env['product.slab.wizard']
        to_num = self.from_num + 2
        if self.to_num:
            to_num = self.to_num
        for i in range(self.from_num, to_num):

            m2 = self.long * self.height * 0.0001
            if self.kl1 and self.kh1:
                k1m2 = self.kl1 * self.kh1 * 0.0001
                m2 = m2 - k1m2
            if self.kl2 and self.kh2:
                k2m2 = self.kl2 * self.kh2 * 0.0001
                m2 = m2 - k2m2

            data = {
                'product_id': self.product_id.id,
                'part_num': self.part_num,
                'sequence': i,
                'long': self.long,
                'height': self.height,
                'kl1': self.kl1,
                'kl2': self.kl2,
                'kh1': self.kh1,
                'kh2': self.kh2,
                'm2': m2,
            }
            new_slab = new_slab_ids.new(data)
            new_slab_ids += new_slab
        self.slab_ids += new_slab_ids

        self.from_num = self.to_num + 1
        self.to_num = False
        self._onchange_slab_ids()

        return {
            'context': self.env.context,
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': self._name,
            'res_id': self.id,
            'view_id': False,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }

    @api.multi
    def _get_res_model(self):
        self.ensure_one()
        res_model = self._context.get('res_model', False)
        res_id = self._context.get('res_model', False)
        if res_model and res_id:
            return self.env[res_model].browse(res_id)

        raise ValueError('错误的创建!')

    @api.onchange('slab_ids')
    def _onchange_slab_ids(self):
        pcs = len(self.slab_ids)
        part = len(set(self.slab_ids.mapped('part_num')))
        qty = sum(self.slab_ids.mapped('m2'))
        self.update({
            'pcs': pcs,
            'part': part,
            'qty': qty,
        })

    @api.onchange('from_num')
    def _onchange_from_num(self):
        if not self.to_num:
            if self.from_num <= 0:
                self.from_num = 1
            self.to_num = self.from_num + 1

    @api.multi
    def _open_view(self):
        self.ensure_one()
        return {
            'context': self.env.context,
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': self._name,
            'res_id': self.id,
            'view_id': False,
            'type': 'ir.actions.act_window',
            'target': 'new',
        }


class PackageLine(models.TransientModel):
    _name = 'product.slab.wizard'

    product_id = fields.Many2one('product.product', '产品')
    part_num = fields.Integer('夹号')

    sequence = fields.Integer('#')

    long = fields.Integer('长')
    height = fields.Integer('高')
    kl1 = fields.Integer('扣迟长')
    kh1 = fields.Integer('扣迟高')
    kl2 = fields.Integer('扣迟2长')
    kh2 = fields.Integer('扣迟2高')

    m2 = fields.Float('面积')
