# -*- coding: utf-8 -*-
{
    'name': "project4",

    'summary': """
        Short (1 phrase/line) summary of the module's purpose, used as
        subtitle on modules listing or apps.openerp.com""",

    'description': """
        Long description of module's purpose
    """,

    'author': "My Company",
    'website': "http://www.yourcompany.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/master/odoo/addons/base/module/module_data.xml
    # for the full list
    'category': 'Uncategorized',
    'version': '0.1',

    # any module necessary for this one to work correctly
    'depends': ['base', 'mail'],

    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'data/stock_data.xml',
        'data/uom_data.xml',
        'data/ir_sequence_data.xml',

        'views/product_views.xml',
        'views/purchase_views.xml',
        'views/warehouse_views.xml',
        'views/picking_views.xml',
        'views/quant_views.xml',
        'views/invoice_views.xml',
        'views/package_list_views.xml',
        'views/product_slab_views.xml',
        'views/sales_views.xml',

        'wizard/package_list_wizard_views.xml',
    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}