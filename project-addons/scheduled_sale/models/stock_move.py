# -*- coding: utf-8 -*-
# © 2018 Comunitea - Kiko Sánchez <kiko@comunitea.com>
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import api, models, fields

class StockMove(models.Model):
    _inherit = "stock.move"

    deliver_month = fields.Char('Requested month', help="Date format = day/month/year(2 digits)", readonly=True)
    scheduled_sale_id = fields.Many2one('scheduled.sale', 'Schedule order', readonly=True)

    def _prepare_procurement_values(self):
        values = super(StockMove, self)._prepare_procurement_values()
        if self.deliver_month:
            values.update({
                'deliver_month': self.deliver_month,
                'scheduled_sale_id': self.scheduled_sale_id.id})
        return values

    def _get_new_picking_values(self):
        vals = super(StockMove, self)._get_new_picking_values()
        vals.update({
            'deliver_month': self.deliver_month,
            'scheduled_sale_id': self.scheduled_sale_id.id})
        return vals

    def _get_new_picking_domain(self):
        vals = super(StockMove, self)._get_new_picking_domain()
        vals += [('deliver_month', '=', self.deliver_month), ('scheduled_sale_id', '=', self.scheduled_sale_id.id),]
        return vals

