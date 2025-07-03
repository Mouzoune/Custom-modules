

# -*- coding: utf-8 -*-
import imghdr
import urllib
import base64
from select import select

import requests
import json
import itertools
import logging
import time

from woocommerce import API
from urllib.request import urlopen
from odoo.exceptions import UserError, MissingError
from odoo import models, api, fields, _, SUPERUSER_ID, _lt
from odoo.tools import config
from bs4 import BeautifulSoup
config['limit_time_real'] = 10000000
config['limit_time_cpu'] = 600
from odoo.exceptions import MissingError, ValidationError, AccessError, UserError


_logger = logging.getLogger(__name__)


class IrModelAccess(models.Model):
    _inherit = 'ir.model.access'

    @api.model
    def check(self, model, mode='read', raise_exception=True):
        if self.env.su:
            # User root have all accesses
            return True

        if (self._uid == 4 and model in ['product.template', 'product.category']):
            # User root have all accesses
            _logger.error(' === self.env.context.get("dont_send_data_to_wooc_from_write_method") ===')
            _logger.error(self.env.context.get("dont_send_data_to_wooc_from_write_method", False))
            _logger.error(self._uid)
            _logger.error(model)
            return True
        assert isinstance(model, str), 'Not a model name: %s' % (model,)

        # TransientModel records have no access rights, only an implicit access rule
        if model not in self.env:
            _logger.error('Missing model %s', model)

        has_access = model in self._get_allowed_models(mode)

        if not has_access and raise_exception:
            groups = '\n'.join('\t- %s' % g for g in self.group_names_with_access(model, mode))
            document_kind = self.env['ir.model']._get(model).name or model
            msg_heads = {
                # Messages are declared in extenso so they are properly exported in translation terms
                'read': _lt(
                    "You are not allowed to access '%(document_kind)s' (%(document_model)s) records.",
                    document_kind=document_kind,
                    document_model=model,
                ),
                'write':  _lt(
                    "You are not allowed to modify '%(document_kind)s' (%(document_model)s) records.",
                    document_kind=document_kind,
                    document_model=model,
                ),
                'create': _lt(
                    "You are not allowed to create '%(document_kind)s' (%(document_model)s) records.",
                    document_kind=document_kind,
                    document_model=model,
                ),
                'unlink': _lt(
                    "You are not allowed to delete '%(document_kind)s' (%(document_model)s) records.",
                    document_kind=document_kind,
                    document_model=model,
                ),
            }
            operation_error = msg_heads[mode]

            if groups:
                group_info = _("This operation is allowed for the following groups:\n%(groups_list)s", groups_list=groups)
            else:
                group_info = _("No group currently allows this operation.")

            resolution_info = _("Contact your administrator to request access if necessary.")

            _logger.info('Access Denied by ACLs for operation: %s, uid: %s, model: %s', mode, self._uid, model)
            msg = """{operation_error}

{group_info}

{resolution_info}""".format(
                operation_error=operation_error,
                group_info=group_info,
                resolution_info=resolution_info)

            raise AccessError(msg) from None

        return has_access


class ProductProduct(models.Model):
    _inherit = 'product.product'

    woocomm_variant_id = fields.Char('WooCommerce ID')
    woocomm_regular_price = fields.Float('WooCommerce Regular Price')
    woocomm_varient_description = fields.Text('WooCommerce Variant Description')
    woocomm_sale_price = fields.Float('WooCommerce Sales Price')
    woocomm_stock_quantity = fields.Float("WooCommerce Stock Quantity")
    woocomm_stock_status = fields.Char("WooCommerce Stock Status")
    
    is_exported = fields.Boolean('Synced In WooCommerce', default=False)
    
        
#    woocomm_instance_id = fields.Many2one('woocommerce.instance', ondelete='cascade')
    woocomm_instance_id = fields.Many2one('woocommerce.instance', related='product_tmpl_id.woocomm_instance_id', store=True)

    wooc_product_image_id = fields.Many2one('woocommerce.product.image')
    woocomm_variant_ids = fields.One2many("woocommerce.product.variant", "product_variant_id")
    #image_1920_filename = fields.Char()

    catalog_visibility = fields.Selection([
        ('visible', 'Shop and search results — نتائج المتجر والبحث'), ('catalog', 'Shop only — المتجر فقط'),
        ('search', 'Search results only — نتائج البحث فقط'), ('hidden', 'Hidden — مخفي')
    ], default='visible', string="Catalog visibility عرض المنتج")

    @api.depends('list_price', 'price_extra')
    @api.depends_context('uom')
    def _compute_product_lst_price(self):
        to_uom = None
        if 'uom' in self._context:
            to_uom = self.env['uom.uom'].browse(self._context['uom'])

        for product in self:
            if to_uom:
                list_price = product.uom_id._compute_price(product.list_price, to_uom)
            else:
                list_price = product.list_price
            product.lst_price = list_price + product.price_extra

            if product.woocomm_regular_price or product.woocomm_sale_price:
                if product.woocomm_regular_price and not product.woocomm_sale_price:
                    product.lst_price = float(product.woocomm_regular_price)
                if product.woocomm_sale_price:
                    product.lst_price = float(product.woocomm_sale_price)

                
    def _compute_product_price_extra(self):
        for product in self:
            if product.woocomm_variant_id:
                # product.price_extra = int(product.woocomm_regular_price) - int(product.woocomm_sale_price) \
                #     if (product.woocomm_regular_price and product.woocomm_sale_price) else int(product.woocomm_sale_price)\
                #      if product.woocomm_sale_price else int(product.woocomm_regular_price) if product.woocomm_regular_price else\
                #       product.woocomm_regular_price  - product.list_price
                product.price_extra = 0
            else:
                product.price_extra = sum(product.product_template_attribute_value_ids.mapped('price_extra'))

class Product(models.Model):
    _inherit = 'product.template'

    @api.model
    def default_get(self, fields):
        res = super(Product, self).default_get(fields)
        if self.env['woocommerce.instance']._context.get('woocomm_instance_id'):
            res['woocomm_instance_id'] = self.env['woocommerce.instance']._context.get('woocomm_instance_id')

        res['detailed_type'] = "product"

        return res
    name = fields.Char('Name', index='trigram', required=True, translate=False)

    wooc_id = fields.Char('WooCommerce ID')
    woocomm_regular_price = fields.Float('WooCommerce Regular Price')
    woocomm_sale_price = fields.Float('WooCommerce Sale Price')
    woocomm_product_status = fields.Char('WooCommerce Product Status')
    woocomm_product_sku = fields.Char('WooCommerce Product SKU')
    woocomm_product_type = fields.Char('WooCommerce Product Type')
    woocomm_product_weight = fields.Float("WooCommerce Weight")
    woocomm_product_qty = fields.Float("WooCommerce Stock Quantity")

    is_exported = fields.Boolean('Synced In WooCommerce', default=False)
    is_woocomm_product = fields.Boolean('Is WooCommerce Product', default=False)
    is_product_active = fields.Boolean()

    woocomm_instance_id = fields.Many2one('woocommerce.instance', ondelete='cascade')
    woocomm_tag_ids = fields.Many2many("product.tag.woocommerce", relation='product_woocommerce_tags_rel', string="Tags")
    woocomm_variant_ids = fields.One2many("woocommerce.product.variant", "product_template_id")
    woocomm_image_ids = fields.One2many("woocommerce.product.image", "product_template_id")

    woocommerce_state_product_visibility = fields.Selection(
        [('draft', 'Brouillon'), ('publish', 'Publier'), ('reparation', 'Matériel en réparation'), ('endommage', 'Inventaire endommagé'),
         ('reserve', 'Inventaire réservé')], default='publish')
    image_1920_filename = fields.Char()

    catalog_visibility = fields.Selection([
        ('visible', 'Shop and search results — نتائج المتجر والبحث'), ('catalog', 'Shop only — المتجر فقط'),
        ('search', 'Search results only — نتائج البحث فقط'), ('hidden', 'Hidden — مخفي')
    ], default='visible', string="Catalog visibility عرض المنتج")

    def _cron_create_update_product(self):
        _logger.error('||=== _cron_create_update_product ===||')
        wooc_instance = self.env['woocommerce.instance'].search([], limit=1, order='id desc')

    def set_product_status(self):
        ''' Enable or Disable Product'''
        woo_api = self.init_wc_api(self.woocomm_instance_id)

        status = self.env.context.get('status')
        product = woo_api.get("products/%s"%self.wooc_id,)
        if product.status_code == 404:
            self.is_product_active = False
            self.is_exported = False
            self.woocomm_product_status = 'draft'
            self.sudo().env.cr.commit()

            raise MissingError(_("Product Not Exist in WooCommerce, Please export first!!!"))

        data = {"status": status,}

        try:
            result = woo_api.put("products/%s" %self.wooc_id, data)

            if result.status_code == 200:
                result_json = result.json()
                self.woocomm_product_status = result_json['status']
                self.is_product_active = True if result_json['status'] == 'publish' else False

        except Exception as error:
            _logger.info("Product Enable/Disable failed!! \n\n %s" % error)
            raise UserError(_("Please check your connection and try again"))

    def set_product_visibility(self):
        woo_api = self.init_wc_api(self.woocomm_instance_id)
        try:
            result = woo_api.put("products/%s" %self.wooc_id, {"catalog_visibility": self.env.context.get('catalog_visibility')})
            if result.status_code == 200:
                result_json = result.json()
                # self.catalog_visibility = result_json['catalog_visibility']
                self.sudo().env.cr.commit()
        except Exception as error:
            _logger.info("Product Enable/Disable failed!! \n\n %s" % error)
            raise UserError(_("Please check your connection and try again"))


    def write(self, values):
        ctx = dict(self.env.context)
        _logger.error(f"Values it 000 === {values}")
        _logger.error(f"Write it 000 === {self.env.user}")
        self = self.with_user(self.env.ref("base.user_admin")).sudo()

        _logger.error(f'self env context =====> {self.env.context.get("dont_send_data_to_wooc_from_write_method")}')
        # if not values.get('taxes_id'):

        if values.get('catalog_visibility', False) and not self.env.context.get("dont_send_data_to_wooc_from_write_method"):
            _logger.error("catalog_visibility")
            self.with_context(catalog_visibility=values.get('catalog_visibility', False)).set_product_visibility()

        if values.get('woocommerce_state_product_visibility', False) and not self.env.context.get("dont_send_data_to_wooc_from_write_method"):
            _logger.error("woocommerce_state_product_visibility")

            if values.get('woocommerce_state_product_visibility') != 'publish':
                ctx['status'] = 'draft'
                values['is_product_active'] = False
                values['woocomm_product_status'] = 'draft'
                self.with_context(status='draft').set_product_status()
            if values.get('woocommerce_state_product_visibility') == 'publish':
                ctx['status'] = 'publish'
                values['is_product_active'] = True
                values['woocomm_product_status'] = 'publish'
                self.with_context(status='publish').set_product_status()
        # if self.env.context.get("dont_send_data_to_wooc_from_write_method", False):
        super().write(values)
        # else:
        #     super().write(values)
        self.sudo().env.cr.commit()
        _logger.error(f"Write it 222 === {self.env.user}")

        if values.get('image_1920_filename', False) and not self.env.context.get("dont_send_data_to_wooc_from_write_method"):
            # woocomm_instance_id = self.env['woocommerce.instance'].search([], limit=1, order='id desc')
            # wooc_instance = self.env['woocommerce.instance'].search([], limit=1, order='id desc')
            woocomm_instance_id = self.woocomm_instance_id
            woo_api = self.init_wc_api(woocomm_instance_id)
            _logger.error('new image_1920 was added')
            if self.wooc_id:
                data = {}
                base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                #src = f'{base_url}/web/image?model=product.template&id={self.id}&field=image_128'
                src = f'{base_url}/web/image/product.template/{self.id}/image_128/{self.image_1920_filename}'

                data['images'] = [{'src': src}]

                result = woo_api.put("products/%s" % int(self.wooc_id), data)
                if result.status_code == 200:
                    _logger.error('image updated successfully')
                else:
                    _logger.error(f'image not updated {result.json()}')
        _logger.error(f"Write it 333 === {self.env.user}")


    def init_wc_api(self, wooc_instance):
        # wooc_instance = self.env['woocommerce.instance'].search([], limit=1, order='id desc')
#        wooc_instance = self.woocomm_instance_id
        if wooc_instance.is_authenticated:
            try:
                woo_api = API(
                            url=wooc_instance.shop_url,
                            consumer_key=wooc_instance.wooc_consumer_key,
                            consumer_secret=wooc_instance.wooc_consumer_secret,
                            # wp_api=True,
                            version=wooc_instance.wooc_api_version
                        )
                # req_data = woo_api.get("")

                return woo_api
            except Exception as error:
                raise UserError(_("Please check your connection and try again"))
        else :
            raise UserError(_("Connection Instance needs to authenticate first. \n Please try after authenticating connection!!!"))

    # Farid products
    def get_all_products(self, wooc_instance, limit=10):
        woo_api = self.init_wc_api(wooc_instance)
        #existed_products = list(self.env.company.sudo().must_create_update_products.values())

        # exist = self.env['product.template'].sudo().search([('wooc_id', 'in', existed_products)])
        #_logger.error(existed_products)
        url = f"products"
        # url =
        _logger.error(url)
        get_next_page = True
        page = 1
        while get_next_page:
            try:
                products = woo_api.get(url, params={'orderby': 'id', 'order': 'asc','per_page': limit, 'page': page})
                page += 1

            except Exception as error:
                _logger.info('\n\n\n\n  Error Products on page=  %s \n\n\n\n' % (page) )
                time.sleep(2)
                continue

            if products.status_code == 200:
                if products.content:
                    parsed_products = products.json()
                    for product in parsed_products:
                        yield product

                    if len(parsed_products) < limit:
                        get_next_page = False
                else:
                    get_next_page = False
            else:
                get_next_page = False

    def get_all_products_variants(self, p_id, wooc_instance, limit=20):
        woo_api = self.init_wc_api(wooc_instance)

        url = "products/%s/variations" %p_id
        get_next_page = True
        page = 1
        while get_next_page:
            try:
                products = woo_api.get(url, params={'orderby': 'id', 'order': 'asc','per_page': limit, 'page': page})
                page += 1

            except Exception as error:
                _logger.info('\n\n\n\n  Error Products on page=  %s \n\n\n\n' % (page) )
                time.sleep(2)
                continue

            if products.status_code == 200:
                if products.content:
                    parsed_products = products.json()
                    for product in parsed_products:
                        yield product

                    if len(parsed_products) < limit:
                        get_next_page = False
                else:
                    get_next_page = False
            else:
                get_next_page = False

    def import_product(self, wooc_instance, is_force_update = False):
        count = 0

        for p_item in self.get_all_products(wooc_instance, limit=20):
            count = count + 1
            ''' To avoid duplications of products already having wooc_id. '''
            #existed_products = list(self.env.company.sudo().must_create_update_products.values())
            if not is_force_update:
                # existed_products_ids = self.env['product.template'].sudo().browse(existed_products)
                _logger.error(f'woocomm_instance_id.  == {wooc_instance.display_name}')
                exist = self.env['product.template'].sudo().search([('wooc_id', '=', p_item['id']), ('woocomm_instance_id', '=', wooc_instance.id)],limit=1)

                if exist:
                    continue

            _logger.info('\n\n\n  Importing Product =  %s -- %s \n\n' % (p_item['id'], p_item['name']) )
            self.create_product( p_item, wooc_instance)


    def create_product(self, p_item, wooc_instance):
        _logger.error(f'self env context =====> {self.env.context}   {self.env.context.get("dont_send_data_to_wooc_from_write_method")}')
        _logger.error(f'create_product  == {p_item["name"]}.   {wooc_instance.id}. {wooc_instance.display_name}')

        p_tags = []

        dict_p = {}
        dict_p['wooc_id'] = p_item['id'] if p_item['id'] else ''
        dict_p['woocomm_instance_id'] = wooc_instance.id
        dict_p['name'] = p_item['name'] if p_item['name'] else ''
        dict_p['company_id'] = wooc_instance.wooc_company_id.id
        dict_p['type'] = 'product'
        dict_p['woocomm_product_status'] = p_item['status']
        # dict_p['woocomm_product_type'] = p_item['type']
        dict_p['woocomm_product_type'] = 'variable'
        dict_p['woocomm_regular_price'] = float(p_item['regular_price']) if p_item['regular_price'] else 0.0
        dict_p['woocomm_sale_price'] = float(p_item['sale_price']) if p_item['sale_price'] else 0.0

        dict_p['purchase_ok'] = True
        dict_p['sale_ok'] = True
        dict_p['is_exported'] = True
        dict_p['is_woocomm_product'] = True
        dict_p['is_product_active'] = True if p_item['status'] == 'publish' else False
        dict_p['default_code'] = p_item['sku'] if p_item['sku'] else ''

        if p_item['description']:
            dict_p['description'] = p_item['description']
            parsed_desc = BeautifulSoup(p_item['description'], 'html.parser')
            description_converted_to_text = parsed_desc.get_text()
            dict_p['description_sale'] = description_converted_to_text

        if p_item['categories']:
            for cat in p_item['categories']:

                categ = self.env['product.category'].with_user(self.env.ref("base.user_admin")).sudo().search([('wooc_id', '=', cat['id']), ('woocomm_instance_id', '=', wooc_instance.id)], limit=1)
                if categ:
                    dict_p['categ_id'] = categ[0].id
                else:
                    dict_cat = {}
                    dict_cat['wooc_id'] = cat.get('id')
                    dict_cat['name'] = cat.get('name')
                    dict_cat['wooc_cat_slug'] = cat.get('slug')
                    dict_cat['wooc_cat_description'] = cat['description'] if cat.get('description') else ''
                    dict_cat['is_woocomm_category'] = True
                    dict_cat['is_exported'] = True
                    dict_cat['woocomm_instance_id'] = wooc_instance.id

                    category = self.env['product.category'].with_user(self.env.ref("base.user_admin")).sudo().create(dict_cat)
                    dict_p['categ_id'] = category.id

                break

        if p_item['tags']:
            for tag_str in p_item['tags']:
                existing_tag = self.env['product.tag.woocommerce'].sudo().search([('wooc_id', '=', tag_str['id']), ('woocomm_instance_id', '=', wooc_instance.id)], limit=1)
                dict_value = {}
                dict_value['wooc_id'] = tag_str['id']
                dict_value['is_woocomm_tag'] = True
                dict_value['woocomm_instance_id'] = wooc_instance.id
                dict_value['name'] = tag_str['name']

                if not existing_tag:
                    create_tag_value = self.env['product.tag.woocommerce'].sudo().create(dict_value)
                    p_tags.append(create_tag_value.id)
                else:
                    write_tag_value = existing_tag.sudo().write(dict_value)
                    p_tags.append(existing_tag.id)
            dict_p['woocomm_tag_ids'] = [(4, val) for val in p_tags]
        _logger.error(f'====================')

        product = self.env['product.template'].with_user(self.env.ref("base.user_admin")).sudo().search([('wooc_id', '=', p_item['id']), ('woocomm_instance_id', '=', wooc_instance.id)],limit=1)
        _logger.error(f'///////////////. product {product}')

        if not product:
            product = self.env['product.template'].with_user(self.env.ref("base.user_admin")).sudo().with_context(dont_send_data_to_wooc_from_write_method=True).create(dict_p)
        else:
            _logger.error(f'/product////////////// {product} ---')
            
            product.with_user(self.env.ref("base.user_admin")).sudo().with_context(dont_send_data_to_wooc_from_write_method=True).write(dict_p)
        _logger.error('/22222////////////// dont_send_data_to_wooc_from_write_method ---')

        self.with_user(self.env.ref("base.user_admin")).env.cr.commit()

        if p_item['attributes'] and not self.env.context.get("dont_send_data_to_wooc_from_write_method"):
            _logger.error('/22222////////////// dont_send_data_to_wooc_from_write_method ---')

            for attr in p_item['attributes']:

                if attr["id"] == 0:
                    #product custom attribute id is 0 and skip creating custom attribute
                    continue

                product_attr = self.env['product.attribute'].with_context(dont_send_data_to_wooc_from_write_method=True).sudo().create_attribute(attr, wooc_instance)

                p_attr_val = []
                if attr['options'] and attr['variation'] == True:
                    self.env['product.attribute'].with_context(dont_send_data_to_wooc_from_write_method=True).sudo().create_attribute_terms(product_attr, wooc_instance)

                    for value in attr['options']:
                        _logger.error(f'value... {value}')
                        existing_attr_value = self.env['product.attribute.value'].sudo().search(
                            [('name', '=', value),('woocomm_instance_id', '=', wooc_instance.id), '|', ('attribute_id', '=', product_attr.id),  ('woocomm_attribute_id', '=', product_attr.id)])
                        _logger.error(f'existing_attr_value. {existing_attr_value}')
                        p_attr_val.append(existing_attr_value.id)

                    if product_attr:
                        if p_attr_val:
                            exist = self.env['product.template.attribute.line'].sudo().search(
                                [('attribute_id', '=', product_attr.id),
                                    ('value_ids', 'in', p_attr_val),
                                    ('product_tmpl_id', '=', product.id)], limit=1)
                            if not exist:
                                _logger.error('/////////////////////  p_attr_val +++++ /')
                                _logger.error(product_attr)
                                _logger.error(p_attr_val)
                                exist = self.env['product.template.attribute.line'].with_context(dont_send_data_to_wooc_from_write_method=True).sudo().create({
                                    'attribute_id': product_attr.id,
                                    'value_ids': [(6, 0, [p_a for p_a in p_attr_val if p_a])],
                                    'product_tmpl_id': product.id
                                })
                            else:
                                exist.with_context(dont_send_data_to_wooc_from_write_method=True).sudo().write({
                                    'attribute_id': product_attr.id,
                                    'value_ids': [(6, 0, [p_a for p_a in p_attr_val if p_a])],
                                    'product_tmpl_id': product.id
                                })
        _logger.error('/2 PRE ---')

        # syn product images             
        if p_item['images'] and not self.env.context.get("dont_send_data_to_wooc_from_write_method"):
            # set first image as main image
            main_image = True
            for image in p_item['images']:
                if image['src']:
                    self.import_product_images_sync(image,product, False, main_image)
                    main_image = False

        if p_item['variations']:
            self.sudo().with_context(dont_send_data_to_wooc_from_write_method=True).create_product_variations(product, wooc_instance)
        else :
            _logger.error('|| Update product variations ||')

            product_variant = self.env['product.product'].sudo().search([('product_tmpl_id', '=', product.id), ('woocomm_instance_id', '=', wooc_instance.id)])
            if product_variant :
                product_variant.with_context(dont_send_data_to_wooc_from_write_method=True).sudo().write({'woocomm_variant_id' : p_item['id'],
                        'woocomm_instance_id' : wooc_instance.id,
                        'is_exported' : True})

            product.with_context(dont_send_data_to_wooc_from_write_method=True).sudo().write({
                'list_price': float(p_item['price']) if p_item['price'] else 0.0,
                'weight': p_item['weight'] if p_item['weight'] else '',
            })

            # stock_quantity = int(p_item.get('stock_quantity'))
            # if stock_quantity:
            #     InventoryWizard = self.env['stock.change.product.qty'].with_user(SUPERUSER_ID).sudo()
            #     inventory_wizard = InventoryWizard.create({
            #         'product_id': product_variant.id,
            #         'product_tmpl_id': product_variant.product_tmpl_id.id,
            #         'new_quantity': stock_quantity,
            #     })
            #     inventory_wizard.change_product_qty()


        self.env.cr.commit()


    def create_product_variations(self, product, wooc_instance):
        _logger.error('|| Create product variations ||')

        product_variant = self.env['product.product'].sudo().search([('product_tmpl_id', '=', product.id), ('woocomm_instance_id', '=', wooc_instance.id)])

        for variant in self.get_all_products_variants(product.wooc_id, wooc_instance, limit=20):
            variant_options = []
            if variant['attributes']:
                for v_attr in variant['attributes']:
                    variant_options.append(v_attr['option'])

            for v_item in product_variant:
                _logger.error(f'//////////////////// {v_item}')
                v_item = v_item.sudo()

                if v_item.sudo().product_template_attribute_value_ids:
                    list_values = []
                    for rec in v_item.sudo().product_template_attribute_value_ids:
                        list_values.append(rec.name)
                    if set(variant_options).issubset(list_values):
                        v_item.sudo().default_code = variant['sku']
                        v_item.sudo().is_exported = True
                        v_item.sudo().taxes_id = [(6, 0, [])]

                        v_item.sudo().woocomm_instance_id = wooc_instance.id
                        v_item.sudo().woocomm_variant_id = variant['id']
                        v_item.sudo().woocomm_regular_price = float(variant['regular_price']) if variant['regular_price'] else 0.0
                        v_item.sudo().woocomm_sale_price = float(variant['sale_price']) if variant['sale_price'] else 0.0
                        v_item.sudo().woocomm_varient_description = variant['description']
                        v_item.sudo().woocomm_stock_quantity = variant['stock_quantity']
                        v_item.sudo().woocomm_stock_status = variant['stock_status']

                        if variant['image'] and not self.env.context.get("dont_send_data_to_wooc_from_write_method"):
                            if variant['image']['src']:
                                self.import_product_images_sync(variant['image'], v_item, True)

                            self.env.cr.commit()
                        break

            self.wooc_variations_kanban(variant, product, wooc_instance)

        self.env.cr.commit()

    def export_product(self, wooc_instance=False, force_update_product=False, force_update_image=False):
        # wooc_instance = self.env['woocommerce.instance'].search([], limit=1, order='id desc')
        wooc_instance = self.woocomm_instance_id
        woo_api = self.init_wc_api(wooc_instance)
        is_product_exported = False

        selected_ids = self.env.context.get('active_ids', [])
        products_ids = self.sudo().search([('id', 'in', selected_ids), ('woocomm_instance_id', '=', wooc_instance.id)]) or self
        force_update_product = self.env.context.get('from_button_send_to_woocommerce', False)

        if not products_ids:
            raise UserError(_("Please select products!!!"))

        for product in products_ids:

            force_create_kanban  = False

            try:
                #Condition to create only New Product
                if not force_update_product and product.is_exported:
                    continue

                data =  self.product_export_data_generate(wooc_instance, product)
                if data["type"] == 'simple':
                    # add quantity if product type is simple
                    simple_product = self.env['product.product'].sudo().search([('product_tmpl_id', '=', product.id), ('woocomm_instance_id', '=', wooc_instance.id)])
                    stock_quantity = self.env['stock.quant'].sudo().search([('product_id', '=', simple_product.id),('inventory_quantity_set', '=', True)])
                    data.update({"manage_stock" : True, "stock_quantity": stock_quantity.quantity if stock_quantity else 0,
                                 'regular_price': str(product.woocomm_regular_price),'sale_price': str(product.woocomm_sale_price)
                                 })

                _logger.info('\n\n\n\n  export_product=  %s \n\n\n\n' % (data) )

                if product.wooc_id and product.is_exported:
                    result = woo_api.put("products/%s" % int(product.wooc_id), data)
                    if result.status_code in [400, 404]:
                        result = woo_api.post("products", data)
                        # remove old variant_id if product not in woocommerce
                        self.env['product.product'].sudo().search([('product_tmpl_id', '=', product.id), ('woocomm_instance_id', '=', product.woocomm_instance_id.id)]).write({'woocomm_variant_id':False, 'is_exported' : False})
                        self.env['woocommerce.product.image'].sudo().search([('product_template_id', '=', product.id),('product_template_id.woocomm_instance_id', '=', product.woocomm_instance_id.id)]).write({'is_image_synced':False, 'is_variation_update' : False, 'update_only' : True})
                        force_create_kanban = True
                        self.env.cr.commit()

                    result = result.json()
                else:
                    result = woo_api.post("products", data).json()
                    force_create_kanban = True

                if result:
                    is_product_exported = True

                    product.wooc_id = result['id']
                    product.woocomm_regular_price = result['regular_price']
                    product.woocomm_sale_price = result['sale_price']
                    product.is_woocomm_product = True
                    product.woocomm_instance_id = wooc_instance.id
                    product.is_exported = True
                    product.is_product_active = True
                    product.woocomm_product_status = "publish"
                    # product.woocomm_product_type = result['type']
                    product.woocomm_product_type = 'variable'
                    product.default_code = result['sku'] if result['sku'] else ''


                    self.env.cr.commit()
                #create variations
                self.wooc_variations_create(wooc_instance, product)

                if len(product.product_variant_ids) > 1 and (len(product.product_variant_ids) != len(product.woocomm_variant_ids)):
                    #if kanban missing or not created
                    force_create_kanban = True

                if force_create_kanban or not force_update_product:
                    if product.attribute_line_ids and len(product.product_variant_ids) > 1:
                        self.wooc_variations_kanban_create( wooc_instance, product)
                    else:
                        _logger.info("\n\n\nNo Attribute\n\n")

                if force_update_product and force_update_image:
                    _logger.error('///4444444444444444444444444')
                    self.product_image_export(product)

                _logger.info("\n\n\nProduct created/updated successfully\n\n")

            except Exception as error:
                _logger.info("\n\n\n\n Product creation/updation Failed")
                _logger.info('\n\n\n\n Error message: -- %s \n\n\n\n\n' % error)
                raise UserError(_("Please check your connection and try again"))

        if not is_product_exported:
            raise UserError(_("No new Product to Export..!! \nIf trying to export existing product, please tick Force Update Product"))

    def wooc_variations_create(self, wooc_instance, product):
        woo_api = self.init_wc_api(wooc_instance)
        product_variant = self.env['product.product'].sudo().search([('product_tmpl_id', '=', product.id), ('woocomm_instance_id', '=', wooc_instance.id)])
        product_wooc_id = product.wooc_id

        for variant in product_variant:
            has_attribute = False
            stock_quantity = self.env['stock.quant'].sudo().search([('product_id', '=', variant.id),('inventory_quantity_set', '=', True), ('product_id.woocomm_instance_id', '=', wooc_instance.id)])

            if  not variant.woocomm_variant_id and not variant.is_exported:
                data = { "regular_price": "%s"%variant.lst_price, "manage_stock" : True, "stock_quantity": stock_quantity.quantity if stock_quantity else 0}
                attr_list = []

                if variant.product_template_attribute_value_ids:
                    has_attribute = True
                    for rec in variant.product_template_attribute_value_ids:
                        attr_list.append({"id" : rec.attribute_id.wooc_id, "option" : rec.name,})

                    data.update({"attributes": attr_list})

                wc_variation = woo_api.post("products/%s/variations"%product_wooc_id, data).json()

                if wc_variation:
                    wooc_variant = self.env['woocommerce.product.variant'].sudo().search([('product_template_id', '=', product.id),("product_variant_id", "=", variant.id), ('woocomm_instance_id', '=', wooc_instance.id)])
                    data = {"wooc_id" : wc_variation["id"], "woocomm_instance_id" : wooc_instance.id, "product_template_id" : product.id,"product_variant_id": variant.id, "is_manage_stock" : wc_variation["manage_stock"], "wooc_stock_quantity": wc_variation["stock_quantity"], }

                    if wooc_variant:
                        wooc_variant.with_user(self.env.ref("base.user_admin")).sudo().write(data)
                    else:
                        #create variant only if attribute exist
                        if has_attribute:
                            self.env['woocommerce.product.variant'].with_user(self.env.ref("base.user_admin")).sudo().create(data)

                    variant.with_user(self.env.ref("base.user_admin")).sudo().write({'woocomm_variant_id' : wc_variation["id"],
                                   'woocomm_regular_price' : wc_variation["regular_price"],
                                   'woocomm_sale_price' : wc_variation["sale_price"],
                                   'is_exported' : True})
        self.env.cr.commit()

    def wooc_variations_kanban_create(self, wooc_instance, product):

        for variation in self.get_all_products_variants(product.wooc_id, wooc_instance, limit=20):
            self.wooc_variations_kanban(variation, product, wooc_instance)

    def wooc_variations_kanban(self, variation, product, wooc_instance):
        v_name = ""
        variant_options = []
        if variation['attributes']:
            for v_attr in variation['attributes']:
                variant_options.append(v_attr['option'])
            v_name = " x ".join(variant_options)

        data = {"wooc_id" : variation["id"],
                "name" : v_name,
                "wooc_sku" : variation["sku"],
                "wooc_regular_price" : variation["regular_price"],
                "wooc_stock_quantity" : variation["stock_quantity"],
                "wooc_stock_status" : variation["stock_status"],
                "wooc_variant_description" : variation["description"],
                "is_enabled" : True,
                "is_manage_stock" : variation["manage_stock"],
                "product_template_id" : product.id,
                }

        p_variant = self.env['product.product'].sudo().search([('product_tmpl_id', '=', product.id),("woocomm_variant_id", "=", variation["id"]), ('woocomm_instance_id', '=', wooc_instance.id)])
        if p_variant:
            data.update({"product_variant_id": p_variant.id})
            variant_exist = self.env['woocommerce.product.variant'].sudo().search([('product_template_id', '=', product.id),("product_variant_id", "=", p_variant.id)])
        else:
            variant_exist = self.env['woocommerce.product.variant'].sudo().search([('product_template_id', '=', product.id),("wooc_id", "=", variation["id"])])

        if variant_exist:
            variant_exist.with_user(self.env.ref("base.user_admin")).sudo().write(data)
        else:
            self.env['woocommerce.product.variant'].sudo().create(data)

        self.env.cr.commit()


    def product_export_data_generate(self, wooc_instance, product):

        data = {'name': "%s"%product.name,
                'type': "simple",
                'status': "publish",
                'description': product.description or "",
                'regular_price': "%s"%product.list_price,
                }

        if product.categ_id:
            if product.categ_id.wooc_id:
                data.update({"categories": [{"id" : product.categ_id.wooc_id, "name": product.categ_id.name}]})

        option_list = []
        if product.attribute_line_ids:
            for attr in product.attribute_line_ids:
                val_list = []
                if not attr.attribute_id.wooc_id:
                    self.env['product.attribute'].wooc_attribute_create(wooc_instance, attr.attribute_id)

                for val in attr.value_ids:
                    val_list.append(val.name)

                attr_vals = {
                    "id": attr.attribute_id.wooc_id,
                    "options": val_list,
                    'visible': True,
                    'variation': True if len(val_list) > 1 else False,
                }
                if attr_vals["variation"]:
                    data["type"] = "variable"

                option_list.append(attr_vals)

            data.update({"attributes": option_list})

        return data

    #To update images to the woocommerce, 
    def product_image_export(self, product):
        image_list = self.env['woocommerce.product.image'].sudo().search([('product_template_id', '=', product.id), ('product_template_id.woocomm_instance_id', '=', product.woocomm_instance_id.id)])
        woo_api = self.init_wc_api(product.woocomm_instance_id)
        extra_check = False
        _logger.error('///|||||||||||  product_image_export')
        # woocomm_instance_id = self.env['woocommerce.instance'].search([], limit=1, order='id desc')
        # wooc_instance = self.env['woocommerce.instance'].search([], limit=1, order='id desc')
        woocomm_instance_id = self.woocomm_instance_id
        w_product = woo_api.get("products/%s" %(str(product.wooc_id)))
        if w_product.status_code == 200:
            w_product = w_product.json()

            if len(image_list):
                image_id_list = []
                new_data = {"images": [], }
                for image in image_list:
                    if requests.get(woocomm_instance_id.shop_url + "?p=%s"%image.wooc_id):
                        if image.is_main_image:
                            new_data['images'].insert(0, {'id': image.wooc_id})
                        else:
                            new_data['images'].append({'id': image.wooc_id})
                    else:
                        extra_check = True
                        image_id_list.append(image.id)
                        image.is_image_synced = False

                if extra_check:
                    image_list_new = self.env['woocommerce.product.image'].sudo().search([('id', 'in', image_id_list), ('product_template_id.woocomm_instance_id', '=', self.woocomm_instance_id.id) ])
                    for image in image_list_new:
                        if requests.get(woocomm_instance_id.shop_url + "?p=%s"%image.wooc_id):
                            new_data['images'].append({'id': image.wooc_id})

                img_update = woo_api.put("products/%s" %(product.wooc_id), new_data)

                if img_update.status_code == 400:
                    _logger.info('\n\n\n\n 400 Error: -- %s \n\n\n\n\n' % img_update.json())

                if img_update.status_code == 200:
                    image_list = self.env['woocommerce.product.image'].sudo().search([('product_template_id', '=', product.id), ('product_template_id.woocomm_instance_id', '=', self.woocomm_instance_id.id) ])
                    var_img_data = {"update": [], }
                    for image in image_list:
                        for var_img in image.product_image_variant_ids:
                            var_img_data["update"].append({"id": var_img.woocomm_variant_id,"image": {"id" : image['wooc_id']}  })

                    img_update = woo_api.put("products/%s/variations/batch" % (str(product.wooc_id)), var_img_data)
        _logger.error('///|||||||||||  product_image_export')

        return


    def get_wooc_product_data(self, product_id, wooc_instance):
        woo_api = self.init_wc_api(wooc_instance)
        wc_product = woo_api.get("products/%s"%product_id,)

        if wc_product.status_code == 200:
            if wc_product.content:
                product_data = wc_product.json()
                self.create_product(product_data, wooc_instance)

        return False

    def import_product_images_sync(self, image, product, is_variant = False, is_main_image = False):
        try:
            response = requests.get(image['src'])

            if imghdr.what(None, response.content) != 'webp':
                image_data = base64.b64encode(requests.get(image['src']).content)
                product_template_id = product.product_tmpl_id.id if is_variant else product.id
                img_vals = {"wooc_id": image['id'],
                        "name" : image['name'],
                        "wooc_url" : image['src'],
                        "wooc_image" : image_data,
                        "product_template_id" : product_template_id,
                        "is_image_synced" : True,
                        "is_variation_update" : False,
                        "is_import_image" : True,
                        "is_main_image" : is_main_image,
                        }

                ext_image = self.env['woocommerce.product.image'].sudo().search(
                    [('wooc_id', '=', img_vals['wooc_id']),('product_template_id', '=', product_template_id), ('product_template_id.woocomm_instance_id', '=', product.product_tmpl_id.woocomm_instance_id.id if is_variant else product.woocomm_instance_id.id)], limit=1)


#                    [('wooc_id', '=', img_vals['wooc_id']),('product_template_id', '=', product_template_id), ('product_template_id.woocomm_instance_id', '=', product_template_id.woocomm_instance_id.id)], limit=1)

                if is_variant:
                    ext_id_list = [v_id.id for v_id in ext_image.product_image_variant_ids]
                    if int(product.id) not in ext_id_list:
                        id_list = []
                        id_list.append((4, int(product.id)))
                        img_vals.update({'product_image_variant_ids':id_list})

                if not ext_image:
                    ext_image = self.env['woocommerce.product.image'].sudo().create(img_vals)
                else:
                    ext_image.sudo().with_user(self.env.ref("base.user_admin")).write(img_vals)

                self.env.cr.commit()
        except Exception as error:
            _logger.info('\n\n\n\n  variant image error =  %s \n\n\n\n' % (error) )
            pass


    def woocomm_product_quantity_update(self, wooc_instance=None):

        # wooc_instance = self.env['woocommerce.instance'].search([], limit=1, order='id desc')
        wooc_instance = self.woocomm_instance_id

        woo_api = self.init_wc_api(wooc_instance)

        selected_ids = self.env.context.get('active_ids', [])
        products_ids = self.sudo().search([('id', 'in', selected_ids), ('woocomm_instance_id', '=', wooc_instance.id)])

        if not products_ids:
            raise UserError(_("Please select products!!!"))

        var_quant_data = {"update": [], }
        for product in products_ids:
            p_type = product.woocomm_product_type

            _logger.error(f'Product Name {product.display_name}  |  Type {product.woocomm_product_type}')
            #p_type = 'variable'
            p_variants = self.env['product.product'].sudo().search([('product_tmpl_id', '=', product.id), ('woocomm_instance_id', '=', wooc_instance.id)])
            for variant in p_variants:
                stock_quantity = self.env['stock.quant'].sudo().search([('product_id', '=', variant.id),('location_id', '=', 8), ('quantity', '>=', 0), ('product_id.woocomm_instance_id', '=', wooc_instance.id)], limit=1)
                _logger.error(f'==== stock_quantity.available_quantity =>  {stock_quantity.available_quantity}')
                var_quant_data["update"].append({"id": variant.woocomm_variant_id if p_type == "variable" else product.wooc_id,"stock_quantity": stock_quantity.available_quantity if stock_quantity else 0, "manage_stock" : True })

            if p_type == "variable":
                stock_quantity_update = woo_api.put("products/%s/variations/batch" % (str(product.wooc_id)), var_quant_data)
            elif p_type == "simple":
                stock_quantity_update = woo_api.put("products/batch", var_quant_data)


class ProductTag(models.Model):
    _description = "Product Tag"
    _name = 'product.tag.woocommerce'

    wooc_id = fields.Char('WooCommerce ID')
    name = fields.Char('Tag name')    
    is_woocomm_tag = fields.Boolean(string='Is WooCommerce Tag?')
    woocomm_instance_id = fields.Many2one('woocommerce.instance', ondelete='cascade')
        
