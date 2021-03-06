# -*- coding: utf-8 -*-
# © 2018 Comunitea - Kiko Sánchez <kiko@comunitea.com>
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import _, api, fields, models
from odoo.osv import expression

class ScheduleSalePeriod(models.Model):
    _name = 'scheduled.sale.period'

    active = fields.Boolean('Active', default=True)
    name = fields.Char('Name', required=True)
    from_date = fields.Date('From date', required=True)
    to_date = fields.Date('To date', required=True)
    scheduled_sale_ids = fields.One2many('scheduled.sale', 'period_id', string="Orders")


class ScheduleSale(models.Model):

    _name = 'scheduled.sale'
    _description = 'Schedule sale'

    @api.multi
    @api.depends('scheduled_orders_ids')
    def _compute_sale_orders_count(self):
        for order in self:
            order.scheduled_orders_ids_count = len(order.scheduled_orders_ids)
            order.scheduled_order_lines_ids_count = len(order.scheduled_order_lines_ids)


    @api.multi
    @api.depends('product_ids')
    def _compute_product_count(self):
        for order in self:
            order.product_ids_count = len(order.product_ids)

    name = fields.Char('Name', required=True)
    code = fields.Char('Code')
    active = fields.Boolean('Active', default=True)
    period_id = fields.Many2one('scheduled.sale.period', string="Period",
                                states = {'confirm': [('readonly', True)], 'done': [('readonly', True)]})
    company_id = fields.Many2one('res.company', 'Company',
                                 default=lambda self: self.env['res.company']._company_default_get('scheduled.sale'),
                                 states={'confirm': [('readonly', True)], 'done': [('readonly', True)]})

    pricelist_id = fields.Many2one('product.pricelist', string='Pricelist', required=True, readonly=False,
                                   help="Pricelist for scheduled sale.",
                                   states={'confirm': [('readonly', True)], 'done': [('readonly', True)]})

    product_brand_id = fields.Many2one('product.brand', string='Brand')
    product_ids = fields.One2many('product.product', 'scheduled_sale_id',
                     string="Products in this schedule")

    product_ids_archived = fields.One2many('product.product', 'scheduled_sale_id',
                                  string="Archived products in this schedule", domain=[('active', '=', False)])

    product_ids_count = fields.Integer('Product count', compute='_compute_product_count')
    state = fields.Selection([
        ('cancel', 'Cancelled'),
        ('draft', 'Draft'),
        ('confirm', 'Confirmed'),
        ('done', 'Ended')
        ], 'Status', default='draft', index=True, required=True, track_visibility='always')

    scheduled_orders_ids = fields.One2many('sale.order', 'scheduled_sale_id', string="Orders")
    scheduled_orders_ids_count = fields.Integer('Sale orders count', compute='_compute_sale_orders_count')
    scheduled_order_lines_ids = fields.One2many('sale.order.line', 'scheduled_sale_id', string="Orders")
    scheduled_order_lines_ids_count = fields.Integer('Sale orders count', compute='_compute_sale_orders_count')

    autoconfirm_sales = fields.Boolean("Auto confirm sales", help="If checked, the associated sale orders are confirmed when this schedule is done")
    autounlink_products = fields.Boolean("Auto unlink product", help="If checked, when done, unlink inactive product templates")

    @api.multi
    def _cancel_schedule(self):
        for self_id in self:
            self_id.state = 'cancel'
            self_id.scheduled_orders_ids.action_cancel()
        return True

    @api.multi
    def cancel_schedule(self):
        return self._cancel_schedule()


    @api.multi
    def _done_schedule(self):
        for schedule in self:
            schedule.state = 'done'
            #COnfirmo los pedidos ????
            if schedule.autoconfirm_sales:
                schedule.scheduled_orders_ids.filtered(lambda x:x.state in ('draft', 'sent')).action_confirm()
            if schedule.autounlink_products:
                template_to_schedule = self.env['product.template'].search([('scheduled_sale_id', '=', schedule.id),('active', '=', False)])
                template_to_schedule.unlink()
        return True

    @api.multi
    def done_schedule(self):
        return self._done_schedule()

    @api.multi
    def write(self, vals):
        if 'state' in vals and vals.get('state', '') == 'cancel':
            self.mapped('scheduled_orders_ids').action_cancel()

        return super(ScheduleSale, self).write(vals)

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        # Make a search with default criteria
        names1 = super(models.Model, self).name_search(
            name=name, args=args, operator=operator, limit=limit)
        # Make the other search
        names2 = []
        if name:
            domain = [('code', '=ilike', name + '%')]
            names2 = self.search(domain, limit=limit).name_get()
        # Merge both results
        return list(set(names1) | set(names2))[:limit]


    @api.multi
    def action_show_schedule_orders(self):
        action = self.env.ref(
            'scheduled_sale.action_scheduled_sale_orders_tree').read()[0]
        sale_ids = self.mapped('scheduled_orders_ids')
        if not sale_ids or len(sale_ids) > 1:
            action['domain'] = "[('id','in',%s)]" % (sale_ids.ids)
        elif len(sale_ids) == 1:
            res = self.env.ref('sale.view_order_form', False)
            action['views'] = [(res and res.id or False, 'form')]
            action['res_id'] = sale_ids.id

        action['context'] = {'default_scheduled_sale_id': self.id,
                             'default_origin': self.code,
                             'default_validity_date': self.period_id.to_date}
        return action

    @api.multi
    def open_all_product_to_cancel(self):
        return self.open_product_to_cancel(all_products=True)

    @api.multi
    def open_product_to_cancel(self, cancel_ids=[], all_products=False, re_order=False):

        to_cancel_product_ids = [
            (0, 0, dict(product_id=product.id, to_cancel=True, product_tmpl_id=product.product_tmpl_id.id)) for product
            in self.product_ids_archived]
        origin_product_ids = [
            (0, 0, dict(product_id=product.id, to_cancel=False, product_tmpl_id=product.product_tmpl_id.id)) for product
            in self.product_ids]

        wzd_vals = dict(scheduled_sale_id=self.id,
                        to_cancel_product_ids=to_cancel_product_ids,
                        origin_product_ids=origin_product_ids)

        new = self.env['unlink.schedule.product.wzd'].create(wzd_vals)
        if all_products:
            view = self.env.ref('scheduled_sale.unlink_scheduled_product_tree')
            return {
                'name': 'Unlink products Operations',
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'tree',
                'res_model': 'unlink.schedule.product.line',
                'views': [(view.id, 'tree')],
                'view_id': view.id,
                'target': 'self',
                'domain': [('id', 'in', new.to_cancel_product_ids.ids + new.origin_product_ids.ids)],
                'context': dict(self.env.context)}

        else:
            view = self.env.ref('scheduled_sale.unlink_schedule_product_form')
            if cancel_ids:
                new.origin_product_ids.filtered(lambda x: x.product_id.id in cancel_ids).write({'to_cancel': True})
            if re_order:
                new.to_cancel_product_ids.filtered(lambda x: x.product_id.id in cancel_ids).write({'to_cancel': False})
            return {
                'name': 'Unlink products Operations',
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'unlink.schedule.product.wzd',
                'views': [(view.id, 'form')],
                'view_id': view.id,
                'target': 'new',
                'res_id': new.id,
                'context': dict(self.env.context)}
        return action

    def add_args_to_product_search(self, args):
        args = expression.AND([expression.normalize_domain(args), [('scheduled_sale_id', '=', self.id)]])
        return args


    def get_scheduled_sale_by_context(self):

        scheduled_order_by_context = self._context.get('scheduled_sale_id', False) and self.browse(self._context['scheduled_sale_id'])
        return scheduled_order_by_context

    @api.multi
    def action_view_order_lines(self):
        self.ensure_one()
        model_data = self.env['ir.model.data']
        tree_view = model_data.get_object_reference(
            'sale_order_line_tree', 'sale_order_line_tree_view')

        action = self.env.ref(
            'sale_order_line_tree.sale_order_line_tree_view_action').read()[0]

        action['views'] = {
            (tree_view and tree_view[1] or False, 'tree')}

        action['domain'] = [('scheduled_sale_id', '=', self.id)]

        action['context'] = {
            'default_scheduled_sale_id': self.id,
            'pricelist': self.pricelist_id,
            'company_id': self.company_id.id,

        }
        # action['view_ids'] = [tree_view and tree_view[1]]
        action.update(
            {'tax_id': {'domain': [('type_tax_use', '=', 'sale'),
                                   ('company_id', '=', self.company_id)]}}
        )

        return action