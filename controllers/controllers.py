# -*- coding: utf-8 -*-
from odoo import http

# class Project4(http.Controller):
#     @http.route('/project4/project4/', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/project4/project4/objects/', auth='public')
#     def list(self, **kw):
#         return http.request.render('project4.listing', {
#             'root': '/project4/project4',
#             'objects': http.request.env['project4.project4'].search([]),
#         })

#     @http.route('/project4/project4/objects/<model("project4.project4"):obj>/', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('project4.object', {
#             'object': obj
#         })