# -*- coding: utf-8 -*-
# from odoo import http


# class GestionAgenceImmobiliere(http.Controller):
#     @http.route('/gestion_agence_immobiliere/gestion_agence_immobiliere', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/gestion_agence_immobiliere/gestion_agence_immobiliere/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('gestion_agence_immobiliere.listing', {
#             'root': '/gestion_agence_immobiliere/gestion_agence_immobiliere',
#             'objects': http.request.env['gestion_agence_immobiliere.gestion_agence_immobiliere'].search([]),
#         })

#     @http.route('/gestion_agence_immobiliere/gestion_agence_immobiliere/objects/<model("gestion_agence_immobiliere.gestion_agence_immobiliere"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('gestion_agence_immobiliere.object', {
#             'object': obj
#         })

