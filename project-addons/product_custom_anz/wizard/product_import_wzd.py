# © 2018 Comunitea
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models, fields, _
from odoo.exceptions import UserError
import xlrd
import base64

import logging
_logger = logging.getLogger(__name__)

# Global variable to store the new created templates
template_ids = []

class ProductImportWzd(models.TransientModel):

    _name = 'product.import.wzd'

    name = fields.Char('Importation name', required=True)
    file = fields.Binary(string='File', required=True)
    filename = fields.Char(string='Filename')

    brand_id = fields.Many2one('product.brand', 'Brand')
    categ_id = fields.Many2one('product.category', 'Default product category')
    create_attributes = fields.Boolean('Create attributes/values if neccesary')

    def _get_brand(self, name, create=False):
        if name:
            brand = self.env['product.brand'].search([('name','=ilike',name)])
            brand.ensure_one()
            return brand
        return self.brand_id

    @api.onchange('file')
    def onchange_filename(self):
        if not self.name and self.filename:
            self.name = self.filename and self.filename.split('.')[0]


    def _parse_row_vals(self, row, idx):
        res = {
            'ref_template': str(row[0]),
            'name_temp': row[1],
            'name_color': row[2],
            'name_extra': row[3],
            'attr_name': row[4],
            'brand_id': row[5],
            'attr_val': row[6],
            'ean': row[7],
            'code_attr': row[8],
            'cost': row[9] or 0.0,
            'pvp': row[10] or 0.0,
            'category': row[11],
            'type': row[12],
            'gender': row[13],
            'age': row[14],
            'color': row[15],
            'ecommerce':row[16],
            'description':row[17],
            'tag1': row[18],
            'tag2': row[19],
            'tag3': row[20],
            'tag4': row[21],
            'tag5': row[22],
            'tag6': row[23],
            'tag7': row[24],
            'tag8': row[25],
            'tag9': row[26],
        }

        # Check mandatory values setted
        if not row[7]:
            raise UserError(
                _('Missing EAN in row %s ') % str(idx))
        if not (row[0] and row[1] and row[4] and row[6]):
            raise UserError(
                _('The row %s is missing some mandatory column') % str(idx))
        if not self._get_brand(row[5]):
            raise UserError(
                _('The row %s is missing brand') % str(idx))
        return res

    def _create_xml_id(self, xml_id, res_id, model):
        virual_module_name = 'PT' if model == 'product.template' else 'PP'
        self._cr.execute(
            'INSERT INTO ir_model_data (module, name, res_id, model) \
            VALUES (%s, %s, %s, %s)',
                        (virual_module_name, xml_id, res_id, model))


    def _get_category(self, category_name = False, idx=0):
        if not category_name:
            return self.categ_id
        category = self.env['product.category'].search([('complete_name', '=ilike', category_name)], limit=1)

        categ_id = category or self.categ_id
        if not categ_id:
            raise UserError(
                _('The row %s has wrong category (%s) and not default category') % (str(idx), category_name))
        return categ_id

    def _get_category_ecommerce(self, category_name = False, idx=0):
        categ_ecommerce = False
        if category_name:
            categ_ecommerce = self.env['product.public.category'].search([('name', '=ilike', category_name)], limit=1) or False

        if category_name and not categ_ecommerce:
            raise UserError(
                _('The row %s has wrong category ecommerce (%s)') % (str(idx), category_name))
        if categ_ecommerce:
            return [categ_ecommerce.id]
        else:
            return []

    def _get_existing_template_obj(self, row_vals):
        """
        Get an existing template by xml id or return false
        """
        res = False
        xml_id = 'PT.' + row_vals['ref_template']
        try:
            res = self.env.ref(xml_id)
        except ValueError:
            res = False
        return res


    def _get_product_att(self, value, brand_id, type='type', create=False):
        at_tag = self.env['product.attribute.tag']
        domain = [('product_brand_id', '=', brand_id), ('type', '=', type), ('value', '=', value)]
        tag = at_tag.search(domain, limit=1)
        if not tag and create:
            vals ={'product_brand_id': brand_id,
                   'type': type,
                   'value': value}

            tag = at_tag.create(vals)
            print ("Se ha creado la etiqueta de atributo: {}".format(tag.display_name))
        return tag

    def _get_product_color(self, value, idx=0, create=False):
        attribute_color = False
        if value:
            attribute_color = self.env['product.attribute.value'].search([('is_color','=',True),('name', '=ilike', value)], limit=1) or False

        if value and not attribute_color:
            raise UserError(
                _('The row %s has wrong color (%s)') % (str(idx), value))
        if attribute_color:
            return attribute_color.id
        return None

    def _get_attr_value(self, row_vals, idx, categ_id):
        """
        Get an Existing attribute or raise an error
        """
        if not categ_id:
            categ_id = self._get_category(row_vals['category'], idx)

        domain = [('product_brand_id', '=', self._get_brand(row_vals['brand_id']).id)]
        tag_type_id=tag_age_id=tag_gender_id=False
        if row_vals['type']:
            tag_type_id = self._get_product_att(row_vals['type'], self._get_brand(row_vals['brand_id']).id, 'type', self.create_attributes)
            if tag_type_id:
                domain += [('product_type_id', '=', tag_type_id.id)]
            else:
                domain += [('product_type_id', '=', False)]

        if row_vals['gender']:
            tag_gender_id = self._get_product_att(row_vals['gender'], self._get_brand(row_vals['brand_id']).id,'gender', self.create_attributes)
            if tag_gender_id:
                domain += [('product_gender_id', '=', tag_gender_id.id)]
            else:
                domain += [('product_gender_id', '=', False)]

        if row_vals['age']:
            tag_age_id = self._get_product_att(row_vals['age'], self._get_brand(row_vals['brand_id']).id,'age', self.create_attributes)
            if tag_age_id:
                domain += [('product_age_id', '=', tag_age_id.id)]
            else:
                domain += [('product_age_id', '=', False)]
        attr = self.env['product.attribute'].search(domain, limit=1)
        if not attr:
            if self.create_attributes:
                vals = {#'attribute_category_id': categ_id.id,
                        'product_brand_id': self._get_brand(row_vals['brand_id']).id,
                        'name': row_vals['attr_name'],
                        'product_type_id': tag_type_id and tag_type_id.id,
                        'product_gender_id': tag_gender_id and tag_gender_id.id,
                        'product_age_id': tag_age_id and tag_age_id.id}
                attr = self.env['product.attribute'].create(vals)
                print("Se ha creado el atributo: {}".format(attr.display_name))
            else:
                raise UserError(
                        _('Error: El atributo %s in line %s no existe') % (row_vals['attr_name'], str(idx)))
        domain = [
            ('attribute_id', '=', attr.id),
            '|', ('supplier_code', '=', row_vals['code_attr']), ('name', '=', row_vals['attr_val'])
        ]
        attr_value = self.env['product.attribute.value'].search(domain)
        if not attr_value:
            if self.create_attributes:
                vals = {'attribute_id': attr.id,
                        'name': row_vals['attr_val'],
                        'supplier_code': row_vals['code_attr'] or row_vals['attr_val']}
                attr_value = self.env['product.attribute.value'].create(vals)
                print("Se ha creado el valor {} para el atributo: {}".format(attr_value.display_name, attr.display_name))
            else:
                raise UserError(
                    _('Error getting attribute %s with value %s in line %s: \
                        Not found') % (attr.name, row_vals['attr_val'], str(idx)))
        return attr_value

    def _update_template_attributes(self, template, attr_value):
        """
        Add to the template a new attribute value
        """
        pal = self.env['product.attribute.line']

        domain = [
            ('product_tmpl_id', '=', template.id),
            ('attribute_id', '=', attr_value.attribute_id.id)
        ]
        attr_line = pal.search(domain, limit=1)

        # Create new attr_line
        if not attr_line:
            vals = {
                'attribute_id': attr_value.attribute_id.id,
                'value_ids': [(4, attr_value.id)],
                'product_tmpl_id': template.id
            }
            pal.create(vals)
        # Add new attr value to the attr line
        else:
            attr_line.write({'value_ids': [(4, attr_value.id)]})
    def _get_tags(self, vals):

        def find_tag(tag):
            domain = [('name', '=', tag)]
            s_t = self.env['product.supplier.tag'].search(domain, limit=1)
            if s_t:
                return s_t.tag_id
            return self.env['product.tag'].search(domain, limit=1)

        tag_ids = []
        tag = find_tag(vals['tag1'])
        if tag:
            tag_ids.append(tag.id)

        tag = find_tag(vals['tag2'])
        if tag:
            tag_ids.append(tag.id)

        tag = find_tag(vals['tag3'])
        if tag:
            tag_ids.append(tag.id)
        tag = find_tag(vals['tag4'])
        if tag:
            tag_ids.append(tag.id)
        tag = find_tag(vals['tag5'])
        if tag:
            tag_ids.append(tag.id)
        tag = find_tag(vals['tag6'])
        if tag:
            tag_ids.append(tag.id)
        tag = find_tag(vals['tag7'])
        if tag:
            tag_ids.append(tag.id)
        tag = find_tag(vals['tag8'])
        if tag:
            tag_ids.append(tag.id)
        tag = find_tag(vals['tag9'])
        if tag:
            tag_ids.append(tag.id)

        return tag_ids

    def create_variant(self, template, row_vals, idx):

        pp_pool = self.env['product.product']
        product_name = row_vals['name_temp'] + ' ' + row_vals['name_color'] + row_vals['name_extra']
        categ_id = self._get_category(row_vals['category'], idx)
        attr_value = self._get_attr_value(row_vals, idx, categ_id)

        code_attr = attr_value.supplier_code or row_vals['code_attr'] and str(int(row_vals['code_attr'])) or '%04d' % (attr_value.id)
        default_code = row_vals['ref_template'] + '.' + code_attr

        vals = {
            'name': product_name,
            'default_code': default_code,
            'available_in_pos': False,
            'attribute_value_ids': [(4, attr_value.id)],
            'barcode': str(int(row_vals['ean'])),
            'importation_name': self.name,
            'lst_price': row_vals['pvp'],
            'standard_price': row_vals['cost'],
            'type': 'product'
        }
        if template:
            vals.update(product_tmpl_id=template.id)
        product = pp_pool.create(vals)

        # CREATE PRODUCT XMLID
        self._create_xml_id(
            product.barcode, product.id, 'product.product')
        # WRITE TEMPLATE REF AND XMLID TO THE NEW CREATED TEMPLATE
        if not template:
            template = product.product_tmpl_id
            tags = self._get_tags(row_vals)
            vals = {
                'ref_template': row_vals['ref_template'],
                'importation_name': self.name,
                'product_brand_id': self._get_brand(row_vals['brand_id']).id,
                'categ_id': categ_id.id
            }
            if row_vals['description']:
                vals.update(description=row_vals['description'])
            if row_vals['ecommerce']:
                vals.update(public_categ_ids=[(6,0,self._get_category_ecommerce(row_vals['ecommerce'],idx))])
            if row_vals['color']:
                vals.update(product_color=self._get_product_color(row_vals['color'],idx))
            if tags:
                vals.update(tag_ids=[(6, 0, tags)])

            template.write(vals)
            xml_id = row_vals['ref_template']
            self._create_xml_id(xml_id, template.id, 'product.template')
            template_ids.append(template.id)
            if len(template.product_variant_ids)>1:
                raise UserError(
                    "Linea %s: Plantilla %s. Si la plantilla tiene más de una variante debes de crear variantes y el codigo del atributo debe ser distinto a 'NO'" %(idx, template.display_name))

        # LINK ATTRIBUTE VALUE TO THE TEMPLATE
        self._update_template_attributes(template, attr_value)
        return product

    def import_products(self):
        self.ensure_one()
        _logger.info(_('STARTING PRODUCT IMPORTATION'))

        file = base64.b64decode(self.file)
        book = xlrd.open_workbook(file_contents=file)
        sh = book.sheet_by_index(0)
        created_product_ids = []
        idx = 1
        for nline in range(1, sh.nrows):

            idx += 1
            row = sh.row_values(nline)
            row_vals = self._parse_row_vals(row, idx)
            if row_vals['ref_template'] == "" or row_vals['ref_template'] == 'FIN' or len(row_vals['ref_template']) < 1:
                break
            # If existing template, fail, only templates created from this file
            template = self._get_existing_template_obj(row_vals)
            if template and template.id not in template_ids:
                raise UserError(
                    _('The template %s already exists') % template.name)

            product = self.create_variant(template, row_vals, idx)
            created_product_ids.append(product.id)
            _logger.info(_('IMPORTED PRODUCT %s / %s') % (idx, sh.nrows - 1))

        return self.action_view_products(created_product_ids)

    def action_view_products(self, product_ids):
        self.ensure_one()
        action = self.env.ref(
            'product.product_normal_action_sell').read()[0]
        action['domain'] = [('id', 'in', product_ids)]
        return action
