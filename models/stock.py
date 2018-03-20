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
    part = fields.Integer('夹数', related='package_list_id.part', store=True)
    pcs = fields.Integer('件数', compute='_compute_qty', inverse='_set_pcs', store=True)
    pbom_pcs = fields.Integer('件数')
    qty = fields.Float('数量', compute='_compute_qty', store=True)
    uom = fields.Many2one('product.uom', '单位', related='product_id.uom', store=True)
    package_list_id = fields.Many2one('package.list', string='码单')
    package_list_visible = fields.Boolean('显示码单', related='product_id.package_list_visible', readonly=True)

    @api.depends('product_id.type', 'pbom_pcs', 'package_list_id.qty', 'package_list_id.pcs')
    def _compute_qty(self):
        for record in self:
            if record.product_id.type == 'slab':
                record.qty = record.package_list_id.qty or 0
                record.pcs = record.package_list_id.pcs
            elif record.product_id.type == 'block':
                record.qty = record.product_id.single_qty
                record.pcs = 1
            elif record.product_id.type == 'pbom':
                record.pcs = record.pbom_pcs
                record.qty = record.pcs * record.product_id.single_qty

    def _set_pcs(self):
        for record in self:
            if record.product_id.type == 'pbom' or not record.product_id:
                record.pbom_pcs = record.pcs

    @api.onchange('pcs', 'qty', 'package_list_id')
    def onchange_qty(self):
        vals = {}
        if self.product_id:
            if self.product_id.type == 'block':
                pcs = 1
                qty = self.product_id.single_qty * pcs
                vals.update({'qty': qty, 'pcs': pcs})
            elif self.product_id.type == 'slab':
                if self.package_list_id:
                    qty = self.package_list_id.qty
                    pcs = self.package_list_id.pcs
                    vals.update({'qty': qty, 'pcs': pcs})

            self.update(vals)

    @api.onchange('product_id')
    def onchange_package_list_visible(self):
        if not self.product_id:
            return {}
        if self.product_id.type == 'slab':
            self.package_list_visible = True
        else:
            self.package_list_visible = False
    #
    # @api.model
    # def create(self, vals):
    #     if vals.get('package_list_id'):
    #         package_list = self.env['package.list'].browse(vals['package_list_id'])
    #         vals.update({
    #             'qty': package_list.qty,
    #             'pcs': package_list.pcs,
    #             'part': package_list.part,
    #         })
    #
    #     elif vals.get('pcs') and vals.get('product_id'):
    #         product = self.env['product.product'].browse(vals['product_id'])
    #         if product.type == 'pbom':
    #             vals.update({
    #                 'qty': product.single_qty * vals['pcs'],
    #                 'pcs': vals['pcs'],
    #             })
    #         elif product.type == 'block':
    #             vals.update({
    #                 'qty': product.single_qty,
    #                 'pcs': 1,
    #             })
    #     return super(AbsComputeQty, self).create(vals)

    # @api.multi
    # def write(self, vals):
    #     package_list = vals.get('package_list_id', '')
    #     pcs = vals.get('pcs', '')
    #     product_id = vals.get('product_id', '')
    #     if package_list:
    #         package_list = self.env['package.list'].browse(package_list)
    #         vals.update({
    #             'qty': package_list.qty,
    #             'pcs': package_list.pcs,
    #             'part': package_list.part,
    #         })
    #     elif product_id:
    #         product = self.env['product.product'].browse(product_id)
    #         if product.type == 'pbom':
    #             if pcs:
    #                 vals.update({
    #                     'qty': product.single_qty * pcs,
    #                     'pcs': pcs,
    #                 })
    #         elif product.type == 'block':
    #             vals.update({
    #                 'qty': product.single_qty,
    #                 'pcs': 1,
    #             })
    #     return super(AbsComputeQty, self).write(vals)

    # if vals.get('package_list_id') and vals.get('pcs'):
    #     package_list = self.env['package.list'].browse(vals['package_list_id'])
    #     vals.update({
    #         'qty': package_list.qty,
    #         'pcs': package_list.pcs,
    #         'part': package_list.part,
    #     })
    #
    # elif vals.get('pcs') and vals.get('product_id'):
    #     product = self.env['product.product'].browse(vals['product_id'])
    #     if product.type == 'pbom':
    #         vals.update({
    #             'qty': product.single_qty * vals['pcs'],
    #             'pcs': vals['pcs'],
    #         })
    #     elif product.type == 'block':
    #         vals.update({
    #             'qty': product.single_qty,
    #             'pcs': 1,
    #         })
    # return super(AbsComputeQty, self).write(vals)
    #


class PickingType(models.Model):
    _name = 'stock.picking.type'
    _description = '作业类型'

    name = fields.Char('作业名称', required=True)
    code = fields.Selection(
        [('incoming', 'Vendors'), ('outgoing', 'Customers'), ('internal', 'Internal'), ('production', 'Production')],
        '作业类型', required=True)
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
        elif self.code == 'production':
            self.default_location_src_id = self.warehouse_id.lot_stock_id.id if self.warehouse_id else False
            self.default_location_dest_id = self.warehouse_id.lot_stock_id.id if self.warehouse_id else False

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

    name = fields.Char('单号', default='/', readonly=True, copy=False)
    picking_type_id = fields.Many2one('stock.picking.type', '作业类型', required=True,
                                      state={'draft': [('readonly', False)]})
    code = fields.Selection(
        [('incoming', 'Vendors'), ('outgoing', 'Customers'), ('internal', 'Internal'), ('production', 'Production')],
        '作业类型', related='picking_type_id.code', store=True)
    default_location_src_id = fields.Many2one('stock.location', string='源库位置',
                                              related='picking_type_id.default_location_src_id', required=True)
    default_location_dest_id = fields.Many2one('stock.location', string='目标库位置',
                                               related='picking_type_id.default_location_dest_id', required=True)
    partner_id = fields.Many2one('res.partner', string='业务伙伴', required=True)
    date = fields.Datetime('日期', default=fields.datetime.now())
    move_ids = fields.One2many('stock.move', string='库存移动', compute='_compute_move_ids')
    state = fields.Selection(
        selection=(
            ('draft', 'Draft'), ('waiting', 'Waiting'), ('confirm', 'Confirm'), ('done', 'Done'), ('cancel', 'Cancel')),
        string='Status', readonly=True, default='draft', copy=False)
    order_line_ids = fields.One2many('stock.picking.line', 'picking_id', '作业明细行')
    order_line2_ids = fields.One2many('stock.picking.line2', 'picking_id', '作业明细行2')
    invoice_ids = fields.One2many('invoice.order', 'picking_id', '账单')
    # show_order_line2 = fields.Boolean('显示line2', compute='_compute_show_order_line2', store=True)

    block_ids = fields.Many2many('product.block', '荒料编号列表', compute='_compute_block_ids',
                                 help='用于产品order_line2_ids中可选的产品')

    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('stock.picking')
        return super(Picking, self).create(vals)

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

    @api.onchange('picking_type_id')
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
    def _check_state(self, change_to_state):
        self.ensure_one()
        if change_to_state == 'confirm':
            if self.state in 'waiting':
                if not self.order_line2_ids:
                    raise UserError('该作业单不能通过审核状态,因为产品行没有内容!')
                line2_block_ids = self.order_line2_ids.mapped('product_id.block_id')
                if self.block_ids != line2_block_ids:
                    raise UserError('该作业单不能通过审核状态,因为产品行的产品荒料编号与原料明细行的产品荒料编号不匹配!')

    @api.multi
    def action_done(self):
        for record in self:
            record.move_ids._action_done()
            record._create_invoice()
        self.write({'state': 'done'})

    @api.multi
    def action_waiting(self):
        self._check_state('waiting')
        self.write({'state': 'waiting'})

    @api.multi
    def action_draft(self):
        self.move_ids.unlink()
        self.write({'state': 'draft'})

    @api.multi
    def action_cancel(self):
        self.move_ids.unlink()
        self.write({'state': 'cancel'})

    @api.multi
    def action_confirm(self):
        for record in self:
            if record.copy == 'production':
                record._check_production()
        self.order_line_ids._action_confirm()
        self.order_line2_ids._action_confirm()
        self._check_state('confirm')
        self.write({'state': 'confirm'})

    @api.multi
    def _check_production(self):
        self.ensure_one()
        line2_block_ids = self.order_line2_ids.mapped('product_id.block_id')
        if line2_block_ids != self.block_ids:
            raise ValidationError('生产成品行与原料编号不符或缺失!')

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

    picking_id = fields.Many2one('stock.picking', '作业单', required=True, readonly=True, copy=False)
    # code = fields.Selection(
    #     [('incoming', 'Vendors'), ('outgoing', 'Customers'), ('internal', 'Internal'), ('production', 'Production')],
    #     '作业类型', related='picking_id.code', store=True)
    product_id = fields.Many2one('product.product', string='产品')
    location_id = fields.Many2one('stock.location', string='库存位置', required=True)
    location_dest_id = fields.Many2one('stock.location', string='目标库位置', required=True)
    # part = fields.Integer('夹数', related='package_list_id.part', store=True)
    # pcs = fields.Integer('件数', compute='_compute_qty', inverse='_set_pcs', store=True)
    # pbom_pcs = fields.Integer('件数')
    # qty = fields.Float('数量', compute='_compute_qty', store=True)
    # uom = fields.Many2one('product.uom', '单位', related='product_id.uom', store=True)
    # package_list_id = fields.Many2one('package.list', string='码单')
    unit_price = fields.Float('单价')
    amount = fields.Float('金额', compute='_compute_total')
    move_ids = fields.One2many('stock.move', 'picking_line_id', '库存移动', readonly=True, copy=False)
    state = fields.Selection(
        selection=(('draft', 'Draft'), ('waiting', 'Waiting'), ('confirm', 'Confirm'), ('done', 'Done')),
        string='Status', readonly=True, default='draft', related='picking_id.state', store=True)
    purchase_line_id = fields.Many2one('purchase.order.line', '采购订单行')
    invoice_line_ids = fields.One2many('invoice.order.line', 'picking_line_id', '账单行')
    sales_line_id = fields.Many2one('sales.order.line', '销售订单行')

    @api.model
    def default_get(self, fields_list):
        res = super(PickingLine, self).default_get(fields_list)
        code = self._context.get('default_code')
        if code == 'production':
            res['location_dest_id'] = self.env.ref('project4.location_production').id
        return res

    @api.depends('qty', 'unit_price')
    def _compute_total(self):
        for line in self:
            line.amount = line.qty * line.unit_price

    def _prepare_stock_move(self, pcs, slab_ids, reserved_quant=False):

        vals = {
            'product_id': self.product_id.id,
            'location_id': reserved_quant.location_id.id if reserved_quant else self.location_id.id,
            'location_dest_id': self.location_dest_id.id,
            'picking_line_id': self.id,
            'pcs': pcs,
            'qty': self.qty
        }
        if slab_ids:
            vals['slab_ids'] = [(6, 0, slab_ids)]
        return vals

    @api.multi
    def _create_stock_move(self):
        for line in self:
            line._update_reserved(line.product_id, line.location_id, line.pcs, line.package_list_id)

    @api.multi
    def _update_reserved(self, product_id, location_id, pcs, package_list_id):
        quants = self.env['stock.quant']._update_reserved(product_id, location_id, pcs, package_list_id.slab_ids)
        if not quants and pcs > 0:
            slab_lst = package_list_id.slab_ids.mapped('id') if package_list_id else []
            return self.env['stock.move'].create(self._prepare_stock_move(pcs=pcs, slab_ids=slab_lst))
        for reserved_quant, reserved_pcs, reserved_slab_ids in quants:
            to_update = self.move_ids.filtered(lambda m: m.location_id.id == reserved_quant.location_id.id)
            if to_update:
                if to_update[0].product_id.type == 'slab':
                    # slab_lst = to_update.mapped('slab_ids.id').append(reserved_slab_ids)
                    slab_lst = []
                    slabs = to_update.mapped('slab_ids')
                    if slabs:
                        slab_lst.append(slabs.mapped('id'))
                    slab_lst.append(reserved_slab_ids)
                    to_update[0].write({'pcs': to_update.pcs + reserved_pcs,
                                        'slab_ids': (6, 0, slab_lst)})
                else:
                    to_update[0].write({'pcs': to_update.pcs + reserved_pcs})

            else:
                self.env['stock.move'].create(self._prepare_stock_move(reserved_quant=reserved_quant, pcs=reserved_pcs,
                                                                       slab_ids=reserved_slab_ids))

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
        self._create_stock_move()

    @api.onchange('location_id')
    def onchange_location_id(self):
        if not self.location_id:
            return {}
        if self.picking_id.picking_type_id.code == 'production':
            product_lst = self.env['product.product'].search(
                [('type', '=', self.picking_id.picking_type_id.orig_product_type)]).mapped('id')
            return {
                'domain': {
                    'product_id': [('id', 'in', product_lst)]
                }
            }
        elif not self.location_id.should_bypass_reservation():
            product_lst = self.location_id.get_available_product_lst()
            return {
                'domain': {
                    'product_id': [('id', 'in', product_lst)]
                }
            }

    def get_domain_slab_ids(self):
        code = self.picking_id.picking_type_id.code
        if code == 'outgoing':
            if self.sales_line_id:
                return self.sales_line_id.on_stock_slab_ids.mapped('id')
        elif code == 'internal':
            quant = self.env['stock.quant']._get_available(self.product_id, self.location_id)
            return quant[1]

    @api.multi
    def action_show_package_list(self):
        self.ensure_one()
        if self.product_id:
            if self.product_id.type != 'slab':
                return {}
        res_model = 'package.list'
        res_id = self.package_list_id.id if self.package_list_id else False
        ctx = self.env.context.copy()
        ctx.update({
            'res_model': self._name,
            'res_id': self.id,
            'default_product_id': self.product_id.id,
        })
        ctx['search_default_group_part_num'] = True
        ctx['domain_slab_ids'] = self.get_domain_slab_ids()

        return {
            'name': 'package list',
            'res_model': res_model,
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': res_id,
            'target': 'new',
            'src_model': self._name,
            'context': ctx
        }


class PickingLine2(models.Model):
    _name = 'stock.picking.line2'
    _inherit = 'stock.picking.line'

    block_id = fields.Many2one('product.block', '荒料编号', required=True)
    thickness_id = fields.Many2one('product.thickness', '厚度规格', required=True)
    move_ids = fields.One2many('stock.move', 'picking_line2_id', '库存移动', readonly=True)

    # package_list_visible = fields.Boolean('显示码单', compute='_compute_package_list_visible')
    #
    # @api.depends('picking_id.picking_type_id.product_type', 'product_id.type')
    # def _compute_package_list_visible(self):
    #     for record in self:
    #         if record.picking_id.picking_type_id.product_type == 'slab' or record.product_id.type:
    #             record.package_list_visible = True
    #         else:
    #             record.package_list_visible = False

    @api.model
    def default_get(self, fields_list):
        res = super(PickingLine2, self).default_get(fields_list)
        code = self._context.get('default_code')
        if code == 'production':
            res['location_dest_id'] = self._context.get('default_location_dest_id')
        return res

    @api.onchange('location_id')
    def onchange_location_id(self):
        if self.picking_id.picking_type_id.product_type == 'slab' or self.product_id.type:
            self.package_list_visible = True
        else:
            self.package_list_visible = False
        if self.picking_id.code == 'production':
            self.location_id = self.env.ref('project4.location_production').id
        if self._context.get('block_ids'):
            block_ids = self._context.get('block_ids')
            block_lst = [id for block in block_ids for id in block[2]]
            return {
                'domain': {'block_id': [('id', 'in', block_lst)]}
            }

    @api.multi
    def _action_confirm(self):
        self._create_product()
        return super(PickingLine2, self)._action_confirm()

    def _prepare_stock_move(self, pcs, slab_ids, reserved_quant=False):

        vals = {
            'product_id': self.product_id.id,
            'location_id': reserved_quant.location_id.id if reserved_quant else self.location_id.id,
            'location_dest_id': self.location_dest_id.id,
            'picking_line2_id': self.id,
            'pcs': pcs
        }

        if slab_ids:
            vals['slab_ids'] = [(6, 0, slab_ids)]
            # package_list = self.env['package.list'].create({'product_id': self.product_id.id,
            #                                                 'slab_ids': [(6, 0, slab_ids)]})
            # vals['package_list_id'] = package_list.id
        return vals

    @api.multi
    def _prepare_product(self):
        return {
            'block_id': self.block_id.id,
            'thickness_id': self.thickness_id.id,
            'type': self.picking_id.picking_type_id.product_type
        }

    @api.multi
    def _create_product(self):
        for record in self:
            if record.package_list_id:
                record.product_id = self.package_list_id.product_id.id
                return
            vals = record._prepare_product()
            product_id = self.env['product.product'].search(
                [('block_id', '=', self.block_id.id), ('thickness_id', '=', self.thickness_id.id),
                 ('type', '=', self.picking_id.picking_type_id.product_type)], limit=1)
            if product_id:
                record.product_id = product_id.id
            else:
                record.product_id = self.env['product.product'].create(vals)

    @api.multi
    def action_show_package_list(self):
        self.ensure_one()
        if not self.package_list_id:
            return self.action_show_package_list_wizard()
        if self.product_id:
            if self.product_id.type != 'slab':
                return {}
        ctx = self.env.context.copy()
        ctx.update({
            'res_model': self._name,
            'res_id': self.id,
            'default_product_id': self.product_id.id,
        })

        res_model = 'package.list'
        res_id = self.package_list_id.id
        ctx['search_default_group_part_num'] = True
        ctx['domain_slab_ids'] = False
        # ctx['domain_slab_ids'] = self.env['product.slab']._get_available_slab(location_id=self.location_id.id,
        #                                                                       lot_id=self.lot_id.id,
        #                                                                       package_list_id=self.package_list_id.id)
        return {
            'name': 'package list',
            'res_model': res_model,
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': res_id,
            'target': 'new',
            'src_model': self._name,
            'context': ctx
        }

    def action_show_package_list_wizard(self):
        if not self.product_id:
            self._create_product()
        ctx = self.env.context.copy()
        ctx.update({
            'res_model': self._name,
            'res_id': self.id,
            'default_product_id': self.product_id.id,
            'search_default_group_part_num': True,
        })

        res_model = 'package.list.wizard'
        res_id = False
        return {
            'name': 'package list',
            'res_model': res_model,
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_id': res_id,
            'target': 'new',
            'src_model': self._name,
            'context': ctx
        }


class StockMove(models.Model):
    _name = 'stock.move'
    _description = '库存移动作业'

    sequence = fields.Integer('序号', default=10)
    picking_line_id = fields.Many2one('stock.picking.line', '作业单明细行')
    picking_line2_id = fields.Many2one('stock.picking.line2', '作业单明细行2')
    orig_move_id = fields.Many2one('stock.move', string='源库存移动')
    location_id = fields.Many2one('stock.location', string='库存位置', readonly=True)
    location_dest_id = fields.Many2one('stock.location', string='目标库位置', readonly=True)
    product_id = fields.Many2one('product.product', string='产品', required=True)
    pcs = fields.Integer('件数', required=True)
    part = fields.Integer('夹数', compute='_compute_qty', store=True)
    qty = fields.Float('数量', required=True, store=True)
    uom = fields.Many2one('product.uom', '单位', related='product_id.uom', readonly=True, store=True)
    # package_list_id = fields.Many2one('package.list', '码单')
    slab_ids = fields.Many2many('product.slab', string='板材')
    state = fields.Selection(selection=(('draft', 'Draft'), ('confirm', 'Confirm'), ('done', 'Done')),
                             string='Status', readonly=True, default='draft')

    # @api.model
    # def create(self, vals):
    #     if vals.get('slab_ids'):
    #         slab_ids = self.env['product.slab'].browse(vals['slab_ids'][0][2])
    #         vals.update({
    #             'qty': sum(slab_ids.mapped('m2')),
    #             'pcs': len(slab_ids),
    #             'part': len(set(slab_ids.mapped('part_num'))),
    #         })
    #
    #     elif vals.get('pcs') and vals.get('product_id'):
    #         product = self.env['product.product'].browse(vals['product_id'])
    #         if product.type == 'pbom':
    #             vals.update({
    #                 'qty': product.single_qty * vals['pcs'],
    #                 'pcs': vals['pcs'],
    #             })
    #         elif product.type == 'block':
    #             vals.update({
    #                 'qty': product.single_qty,
    #                 'pcs': 1,
    #             })
    #     return super(StockMove, self).create(vals)
    #
    # @api.multi
    # def write(self, vals):
    #     slab_ids = vals.get('slab_ids', '')
    #     pcs = vals.get('pcs', '')
    #     product_id = vals.get('product_id', '')
    #     if slab_ids:
    #         slab_lst = self.env['package.list'].browse(slab_ids)
    #         vals.update({
    #             'qty': sum(slab_lst.mapped('m2')),
    #             'pcs': len(slab_lst),
    #             'part': set(len(slab_lst.mapped('part_num'))),
    #         })
    #     elif product_id:
    #         product = self.env['product.product'].browse(product_id)
    #         if product.type == 'pbom':
    #             if pcs:
    #                 vals.update({
    #                     'qty': product.single_qty * pcs,
    #                     'pcs': pcs,
    #                 })
    #         elif product.type == 'block':
    #             vals.update({
    #                 'qty': product.single_qty,
    #                 'pcs': 1,
    #             })
    #     return super(StockMove, self).write(vals)

    @api.constrains
    def required_picking_line_id(self, ):
        for record in self:
            if not record.picking_line_id and not record.picking_line2_id:
                raise ValidationError('该{}没有对应的picking_line,不能创建!')

    # @api.depends('pcs', 'product_id.type', 'slab_ids')
    # def _compute_qty(self):
    #     for record in self:
    #         if record.product_id.type == 'slab':
    #             record.part = len(record.mapped('slab_ids.part_num'))
    #             record.qty = sum(record.mapped('slab_ids.m2'))
    #         elif record.product_id.type == 'pbom':
    #             record.qty = record.pcs * record.product_id.single_qty
    #             record.qty = False
    #         elif record.product_id.type == 'block':
    #             record.qty = record.product_id.single_qty
    #             record.qty = False

    @api.multi
    def _compute_part(self):
        for record in self:
            record.part = len(record.mapped('slab_id.part_num'))

    @api.multi
    def unlink(self):
        for ml in self:
            if ml.state in ('done', 'cancel'):
                raise UserError(_(
                    'You can not delete product moves if the picking is done. You can only correct the done quantities.'))
            # Unlinking a move line should unreserve.
            if not ml.location_id.should_bypass_reservation():
                self.env['stock.quant']._update_reserved(ml.product_id, ml.location_id, -ml.pcs,
                                                         ml.slab_ids)
        return super(StockMove, self).unlink()

    @api.multi
    def _check_available_quant(self, out_moves):
        quant = self.env['stock.quant']
        for om in out_moves:
            available_pcs, available_slab_ids = quant._get_available(om.product_id, om.location_id)
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
            quant._update_reserved(om.product_id, om.location_id, -om.pcs, om.slab_ids)
            quant._update_available(om.product_id, om.location_id, -om.pcs, om.slab_ids)
        for im in in_moves:
            quant._update_available(im.product_id, im.location_dest_id, im.pcs, im.slab_ids)
        self.write({'state': 'done'})
