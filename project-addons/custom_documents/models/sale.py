# © 2018 Comunitea
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class SaleOrder(models.Model):

    _inherit = 'sale.order'

    operating_unit_id = fields.Many2one(
        'operating.unit', related='type_id.operating_unit_id')

