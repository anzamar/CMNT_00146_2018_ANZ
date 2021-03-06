# © 2016 Comunitea - Kiko Sánchez <kiko@comunitea.com>
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html
from odoo import api, models, fields, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.multi
    def _compute_sale_order_line_count(self):
        for order in self:
            order.sale_order_line_count = len(order.order_line)

    sale_order_line_count = fields.Integer(
        'Order line count', compute='_compute_sale_order_line_count')
    sponsored = fields.Boolean(
        'Sponsored', readonly=True,
        states={'draft': [('readonly', False)]}, copy=False)
    bag_decreased = fields.Boolean('Bag decreased', readonly=True, copy=False)

    @api.model
    def create(self, vals):
        res = super(SaleOrder, self).create(vals)
        if res.partner_id.player and res.partner_id.sponsorship_bag > 0:
            res.sponsored = True
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
        partner = self.partner_id.commercial_partner_id
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
            title = _("Risk exceded for %s") % partner.name
            message = exception_msg
            warning = {
                    'title': title,
                    'message': message,
            }
            res['warning'] = warning
        return res

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        if self.partner_id.player and self.partner_id.sponsorship_bag > 0:
            self.sponsored = True
        return super(SaleOrder, self).onchange_partner_id()

    @api.multi
    def post_message_bag(self, mode):
        mode_str = _('increased') if mode == 'increased' else _('decreased')
        self.ensure_one()
        error_msg = _('Bag has been %s in %s') % (mode_str, self.amount_total)
        error_msg2 = _('Bag has been %s in %s due to %s') \
            % (mode_str, self.amount_total, self.name)
        self.message_post(body=error_msg)
        self.partner_id.message_post(body=error_msg2)

    @api.multi
    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        for order in self:
            if order.sponsored:
                if order.amount_total >= order.partner_id.sponsorship_bag:
                    raise UserError(_('You can confirm this order casuse you \
                        reach the sponsored bag'))

                order.partner_id.decrease_bag(self.amount_total)
                order.write({'bag_decreased': True})

                # Posting
                order.post_message_bag('decreased')
        return res

    @api.multi
    def action_cancel(self):
        res = super(SaleOrder, self).action_cancel()
        for order in self:
            if order.sponsored and order.bag_decreased:
                    order.partner_id.decrease_bag(-order.amount_total)
                    order.bag_decreased = False
                    # Posting
                    order.post_message_bag('increased')
        return res

    @api.multi
    def _prepare_invoice(self):
        """
        Propagate ref_check field, to account_invoice_line
        """
        self.ensure_one()
        res = super(SaleOrder, self)._prepare_invoice()
        res.update(sponsored=self.sponsored)
        return res
    
    @api.multi
    def recalculate_prices(self):
        """
        Para las tarifas que muestran el descuento separado, es necesario
        que este también cambie, repetimos el cálculo original pero para el
        descuento.
        """
        res = super().recalculate_prices()
        for line in self.mapped('order_line'):
            dict = line._convert_to_write(line.read()[0])
            if 'product_tmpl_id' in line._fields:
                dict['product_tmpl_id'] = line.product_tmpl_id
            dict['discount'] = 0.0
            line2 = self.env['sale.order.line'].new(dict)
            # we make this to isolate changed values:
            line2._onchange_discount()
            line.discount = line2.discount
        return res



class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    virtual_stock_conservative = fields.Float(
        related="product_id.virtual_stock_conservative",
        string='Virtual Stock Conservative', related_sudo=True)
    ref_change = fields.Boolean('Reference change', default=False)

    @api.multi
    @api.onchange('product_id')
    def product_id_change(self):
        result = super(SaleOrderLine, self).product_id_change()
        # Check if product added is restricted by brand.
        # If restricted sets true ref_check field
        if self._context.get('ref_change_partner_id', False):
            partner_id = self._context.get('ref_change_partner_id', False)
            restricted_product = self.with_context(
                partner_id=partner_id).env['product.product'].search(
                    [('id', '=', self.product_id.id)])
            if not restricted_product:
                self.ref_change = True
            else:
                self.ref_change = False
        return result

    @api.multi
    def _prepare_invoice_line(self, qty):
        """
        Propagate ref_check field, to account_invoice_line
        If sponsored, price 0
        """
        self.ensure_one()
        res = super(SaleOrderLine, self)._prepare_invoice_line(qty)
        res.update(ref_change=self.ref_change)
        if self.order_id.sponsored:
            res.update({'price_unit': self.product_id.standard_price,
                        'discount': 0.0})
        return res
