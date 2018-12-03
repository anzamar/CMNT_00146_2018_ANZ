# © 2016 Comunitea - Kiko Sánchez <kiko@comunitea.com>
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html
from odoo import api, models, fields, _
from odoo.osv import expression


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.multi
    def _compute_sale_order_line_count(self):
        for order in self:
            order.sale_order_line_count = len(order.order_line)

    sale_order_line_count = fields.Integer('Order line count', compute='_compute_sale_order_line_count')

    @api.multi
    def write(self, vals):
        res = super(SaleOrder, self).write(vals)
        if 'type_id' in vals:
            sale_type = self.env['sale.order.type'].search_read([('id', '=', vals['type_id'])], fields=['operating_unit_id'])
            self.order_line.write({'operating_unit_id': sale_type and sale_type[0]['operating_unit_id'][0]})
        return res

    @api.multi
    @api.onchange('partner_id')
    def onchange_partner_id_warning(self):
        """
        Same logic for warning as action_confirm method of partner_sale_risk
        module.
        """
        res = super(SaleOrder, self).onchange_partner_id_warning()

        if not self.partner_id:
            return
        if not res:
            res = {}
        partner = self.partner_id
        exception_msg = ''
        if partner.risk_exception:
            exception_msg += _("Financial risk exceeded.\n")
        elif partner.risk_sale_order_limit and (
                (partner.risk_sale_order + self.amount_total) >
                partner.risk_sale_order_limit):
            exception_msg += _(
                "This sale order exceeds the sales orders risk.\n")
        elif partner.risk_sale_order_include and (
                (partner.risk_total + self.amount_total) >
                partner.credit_limit):
            exception_msg += _(
                "This sale order exceeds the financial risk.\n")
        if exception_msg:
            title = ("Risk exceded for %s") % partner.name
            message = exception_msg
            warning = {
                    'title': title,
                    'message': message,
            }
            res['warning'] = warning
        return res


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    operating_unit_id = fields.Many2one('operating.unit', string="Operating unit")
    virtual_stock_conservative = fields.Float(related="product_id.virtual_stock_conservative",
                                              string='Virtual Stock Conservative')

    requested_date = fields.Date('Requested Date')

    @api.multi
    @api.onchange('product_id')
    def product_id_change(self):
        result = super(SaleOrderLine, self).product_id_change()
        if self.order_id.type_id:
            self.operating_unit_id = self.order_id.type_id.operating_unit_id
        return result

