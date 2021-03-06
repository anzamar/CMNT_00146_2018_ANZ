# -*- coding: utf-8 -*-
# Copyright 2019 Kiko Sánchez, <kiko@comunitea.com> Comunitea Servicios Tecnológicos S.L.
# Copyright 2019 Vicente Gutiérrez, <vicente@comunitea.com> Comunitea Servicios Tecnológicos S.L.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, models, fields
from pprint import pprint

class InventoryLine(models.Model):

    _inherit = "stock.inventory.line"

    def _get_quants(self):
        return self.env['stock.quant'].search([
            '|', ('company_id', '=', self.company_id.id), ('company_id', '=', False),
            ('location_id', '=', self.location_id.id),
            ('lot_id', '=', self.prod_lot_id.id),
            ('product_id', '=', self.product_id.id),
            ('owner_id', '=', self.partner_id.id),
            ('package_id', '=', self.package_id.id)])

   