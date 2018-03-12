# -*- coding: utf-8 -*-

from odoo import models, fields, api

COST_BY_SELECTION = (
    ('weight', '按重量'),
    ('m3', '按立方'),
)
PRODUCT_TYPE_SELECTION = [
    ('block', '荒料'),
    ('slab', '板材'),
    ('pbom', '毛板')
]


class Quarry(models.Model):
    _name = 'product.quarry'

    name = fields.Char('矿口名称', required=True)
    desc = fields.Char('描述')
    SG = fields.Float('比重')

    @api.constrains('name')
    def _unique_name(self):
        for record in self:
            count = record.search_count([('name', '=', record.name)])
            if count > 1:
                raise ValueError('{}已经存在,请确保该编号的唯一性!'.format(record.name))


class Batch(models.Model):
    _name = 'product.batch'

    name = fields.Char("批次编号", required=True, index=True)
    desc = fields.Char('描述')

    @api.constrains('name')
    def _unique_name(self):
        for record in self:
            count = record.search_count([('name', '=', record.name)])
            if count > 1:
                raise ValueError('{}已经存在,请确保该编号的唯一性!'.format(record.name))


class ProductBlock(models.Model):
    _name = 'product.block'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('编号', required=True, index=True)
    quarry_id = fields.Many2one('product.quarry', '矿口')
    batch_id = fields.Many2one('product.batch', '批次')
    category_id = fields.Many2one('product.category', '品种')
    # ------------荒料数据--------------------
    weight = fields.Float('重量', digits=(3, 2), help='单位为:t')
    m3 = fields.Float('立方', digits=(3, 2), compute='_compute_m3', store=True)
    long = fields.Integer('长', help='单位为:cm')
    width = fields.Integer('宽', help='单位为:cm')
    height = fields.Integer('高', help='单位为:cm')
    cost_by = fields.Selection(selection=COST_BY_SELECTION, string='成本计算方式', default='weight')
    cost_unit_price = fields.Float('成本单价')
    SG = fields.Float(related='quarry_id.SG', string='比重')
    cost_qty = fields.Float('计价数量', compute='_compute_qty', store=True, readonly=True)
    cost_uom = fields.Many2one('product.uom', '成本/计价单位', compute='_compute_qty', store=True)
    # cost_uom = fields.Selection(selection=(('t', 't'), ('m3', 'm3')), string='计价单位', default='t',
    #                             compute='_compute_qty',
    #                             readonly=True, store=True)

    _sql_constraints = [('name unique', 'unique(name)', u'该荒料名称已存在!')]

    @api.depends('cost_by', 'm3', 'weight')
    def _compute_qty(self):
        for record in self:
            if record.cost_by == 'weight':
                record.cost_qty = record.weight
                record.cost_uom = self.env.ref('project4.uom_t').id
            else:
                record.cost_qty = record.m3
                record.cost_uom = self.env.ref('project4.uom_m3').id

    @api.depends('long', 'width', 'height', 'weight')
    def _compute_m3(self):
        for r in self:
            if r.cost_by == 'm3':
                if r.long and r.width and r.height:
                    r.m3 = r.long * r.width * r.height * 0.00001
                else:
                    r.m3 = None
            else:
                r.m3 = r.weight / 2.8

    # @api.onchange('long', 'width', 'height', 'weight')
    # def _onchange_m3(self):
    #     for r in self:
    #         if not r.cost_by:
    #             return None
    #         if r.cost_by == 'm3':
    #             if r.long and r.width and r.height:
    #                 r.m3 = r.long * r.width * r.height * 0.00001
    #             else:
    #                 r.m3 = None
    #         else:
    #             r.m3 = r.weight / 2.8


class ProductCategory(models.Model):
    _name = 'product.category'
    _description = "Product Category"
    _parent_name = "parent_id"
    _parent_store = True
    _parent_order = 'name'
    _rec_name = 'compute_name'
    _order = 'parent_left'

    name = fields.Char('名称', index=True, required=True)
    compute_name = fields.Char('名称', compute='_compute_complete_name', store=True)
    parent_id = fields.Many2one('product.category', '上级分类', index=True, ondelete='cascade')
    child_id = fields.One2many('product.category', 'parent_id', '子分类')
    parent_left = fields.Integer('Left Parent', index=1)
    parent_right = fields.Integer('Right Parent', index=1)

    @api.depends('name', 'parent_id.compute_name')
    def _compute_complete_name(self):
        for category in self:
            if category.parent_id:
                category.compute_name = '%s / %s' % (category.parent_id.compute_name, category.name)
            else:
                category.compute_name = category.name


class ProductUom(models.Model):
    _name = 'product.uom'
    _description = '计量单位'

    name = fields.Char('Name', index=True, required=True, translate=True)


class ProductType(models.Model):
    _name = 'product.thickness'
    _description = '产品厚度'

    name = fields.Char('厚度', compute='_compute_name', store=True)
    thickness = fields.Float('厚度数据', help='单位为:cm', index=True, required=True)
    SG = fields.Float('每吨对应平方数')

    _sql_constraints = [('unique thickness', 'unique(thickness)', '该厚度数据已经存在!')]

    @api.depends('thickness')
    def _compute_name(self):
        for r in self:
            r.name = "{}cm".format(r.thickness)


class Product(models.Model):
    _name = 'product.product'
    _description = '产品'

    name = fields.Char('产品名称', compute='_compute_name')
    block_id = fields.Many2one('product.block', '荒料编号', required=True, index=True, ondelete='cascade')
    single_qty = fields.Float('单件数量', compute='_compute_single_qty', store=True)
    type = fields.Selection(PRODUCT_TYPE_SELECTION, '产品类型', required=True)
    uom = fields.Many2one('product.uom', '单位', help="This comes from the product form.", compute='_compute_uom',
                          store=True)
    package_list_visible = fields.Boolean('是否显示码单', compute='_compute_package_list_visible',
                                          readonly=True, store=True)
    thickness_id = fields.Many2one('product.thickness', '厚度')  # 日后用来计算货物重量

    @api.depends('type')
    def _compute_uom(self):
        for r in self:
            if r.type != 'block':
                r.uom = self.env.ref('project4.uom_m2').id
            else:
                r.uom = r.block_id.cost_uom.id

    @api.depends('block_id.name', 'type', 'thickness_id.name')
    def _compute_name(self):
        for r in self:
            type_name = dict(PRODUCT_TYPE_SELECTION)[r.type]
            if r.thickness_id:
                name = '{} / {}{}'.format(r.block_id.name, r.thickness_id.name, type_name)
            else:
                name = '{} / {}'.format(r.block_id.name, type_name)
            r.name = name

    @api.depends('type')
    def _compute_single_qty(self):
        for record in self:
            if record.type != 'slab':
                record.single_qty = record.block_id.cost_qty

    @api.depends('type')
    def _compute_package_list_visible(self):
        for record in self:
            if record.type == 'slab':
                record.package_list_visible = True
            else:
                record.package_list_visible = False

    # @api.depends('block_id')
    # def _compute_qty(self):
    #     for r in self:
    #         if r.
    # is_reserved = fields.Boolean('已保留', default=False)

    # package_list_id = fields.Many2many('package.list', relation='package_slab',string='码单')


class ProductSlab(models.Model):
    _name = 'product.slab'
    _description = '板材规格'

    product_id = fields.Many2one('product.product', '产品名称', domain=[('type', '=', 'slab')], required=True)
    long = fields.Integer('长')
    height = fields.Integer('高')
    kl1 = fields.Integer('扣迟长')
    kh1 = fields.Integer('扣迟高')
    kl2 = fields.Integer('扣迟2长')
    kh2 = fields.Integer('扣迟2高')

    sequence = fields.Integer('#', default=10)
    num = fields.Integer('#', related='sequence', help='用于显示')
    part_num = fields.Integer('夹#', default=1)

    quant_id = fields.Many2one('stock.quant', '库存框', help='查库存地址')
    # location_id = fields.Many2one('stock.location', 'Location', readonly=True)
    m2 = fields.Float('面积', compute='_compute_total')

    @api.depends('long', 'height', 'kl1', 'kh1', 'kl2', 'kh2')
    @api.multi
    def _compute_total(self):
        for record in self:
            m2 = record.long * record.height * 0.0001
            if record.kl1 and record.kh1:
                k1m2 = record.kl1 * record.kh1 * 0.0001
                m2 = m2 - k1m2
            if record.kl2 and record.kh2:
                k2m2 = record.kl2 * record.kh2 * 0.0001
                m2 = m2 - k2m2
            record.m2 = m2


class PackageList(models.Model):
    _name = 'package.list'
    _description = '码单'

    product_id = fields.Many2one('product.product', '产品编号', required=True, index=True, ondelete='cascade')
    block_id = fields.Many2one('product.block', '荒料编号', related='product_id.block_id')
    qty = fields.Float('数量', compute='_compute_total', store=True, readonly=True)
    part = fields.Integer('夹数', compute='_compute_total', store=True, readonly=True)
    pcs = fields.Integer('件数', compute='_compute_total', store=True, readonly=True)
    slab_ids = fields.Many2many('product.slab', string='板材')

    @api.depends('slab_ids')
    def _compute_total(self):
        for record in self:
            qty = sum(record.mapped('slab_ids.qty'))
            part = len(set(record.mapped('slab_ids.part_num')))
            pcs = len(record.slab_ids)
            name = '{}/{}夹/{}件/{}m2'.format(record.lot_id.name, part, pcs, qty)

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
            'qty': sum(self.slab_ids.mapped('qty')),
            'pcs': len(self.slab_ids),
            'part': len(set(self.slab_ids.mapped('part_num'))),
        })
