# -*- coding: utf-8 -*-
import imghdr
import urllib
import base64
import requests
import json
import itertools
import logging
import time

from woocommerce import API
from odoo.exceptions import UserError, MissingError
from odoo import models, api, fields, _
from odoo.tools import config
from bs4 import BeautifulSoup
config['limit_time_real'] = 10000000
config['limit_time_cpu'] = 600

_logger = logging.getLogger(__name__)

class ProductTemplateAttributeLine(models.Model):
    _inherit = 'product.template.attribute.line'

    wooc_id = fields.Char('WooCommerce Attribute Id')
    wooc_slug = fields.Char('WooCommerce Slug')
    
    is_exported = fields.Boolean('Is Exported?')
    
    
class ProductAttribute(models.Model):
    _inherit = 'product.attribute'
    
    @api.model
    def default_get(self, fields):
        res = super(ProductAttribute, self).default_get(fields)
        if self.env['woocommerce.instance']._context.get('woocomm_instance_id'):
            res['woocomm_instance_id'] = self.env['woocommerce.instance']._context.get('woocomm_instance_id')
                   
        return res
    
    wooc_id = fields.Char(string='WooCommerce Attribute Id')
    woocomm_attr_slug = fields.Char(string='WooCommerce Attribute Slug')
    
    is_woocomm = fields.Boolean(string='Is WooCommerce?')
    woocomm_instance_id = fields.Many2one('woocommerce.instance', string='WooCommerce Instance')

    def init_wc_api(self, wooc_instance):
        # wooc_instance = self.env['woocommerce.instance'].search([], limit=1, order='id desc')
#        wooc_instance = self.woocomm_instance_id
        if wooc_instance.is_authenticated:
            try:
                woo_api = API(
                            url=wooc_instance.shop_url,
                            consumer_key=wooc_instance.wooc_consumer_key,
                            consumer_secret=wooc_instance.wooc_consumer_secret,
                            wp_api=True,
                            version=wooc_instance.wooc_api_version
                        )
                req_data = woo_api.get("")
                
                return woo_api
            except Exception as error:
                raise UserError(_("Please check your connection and try again"))
        else :
            raise UserError(_("Connection Instance needs to authenticate first. \n Please try after authenticating connection!!!"))

        
    def get_all_attributes(self, wooc_instance, limit=100):
        woo_api = self.init_wc_api(wooc_instance)
                
        url = "products/attributes"
        get_next_page = True
        page = 1
        while get_next_page:
            try:
                attributes = woo_api.get(url, params={'orderby': 'id', 'order': 'asc','per_page': limit, 'page': page})
                page += 1

            except Exception as error:
                _logger.info('\n\n\n\n  Error Attributes on page=  %s \n\n\n\n' % (page) )
                time.sleep(2)
                continue

            if attributes.status_code == 200:
                if attributes.content:
                    parsed_attributes = attributes.json()
                    for attribute in parsed_attributes:
                        yield attribute
                        
                    if len(parsed_attributes) < limit:
                        get_next_page = False 
                else:
                    get_next_page = False 
            else:
                    get_next_page = False 
              
    def import_attributes(self, wooc_instance, is_force_update = False):

        for attr_item in self.get_all_attributes(wooc_instance, limit=100):
            _logger.info('\n\n\n\n  woocomm attribute =  %s \n\n\n\n' % (attr_item) )
            
            exist = self.env['product.attribute'].sudo().search([('wooc_id', '=', attr_item['id']),('woocomm_instance_id', '=', wooc_instance.id)],limit=1)
            
            if exist:
                continue
            
            p_attr = self.create_attribute( attr_item, wooc_instance)
            _logger.error(f"attr_item.  {attr_item}  p_attr. {p_attr}")

            self.create_attribute_terms(p_attr, wooc_instance)

            self.env.cr.commit()
            # break
        
    def create_attribute(self, attr, wooc_instance):

        dict_attr = {}
        exist_attr = self.env['product.attribute'].sudo().search(
            [('woocomm_instance_id', '=', wooc_instance.id), '|', ('wooc_id', '=', attr['id']),
                ('woocomm_attr_slug', '=', attr['slug'])], limit=1)

        dict_attr['wooc_id'] = attr['id'] if attr['id'] else ''
        dict_attr['woocomm_attr_slug'] = attr['slug'] if attr['slug'] else ''
        dict_attr['name'] = attr['name'] if attr['name'] else ''
        dict_attr['is_woocomm'] = True
        dict_attr['woocomm_instance_id'] = wooc_instance.id

        if not exist_attr:
            exist_attr = self.env['product.attribute'].sudo().create(dict_attr)
        else:
            exist_attr.write(dict_attr)

        self.env.cr.commit()
        return exist_attr

    def create_attribute_terms(self, attr, wooc_instance):
        woo_api = self.init_wc_api(wooc_instance)
        attr_id = attr.wooc_id
        _logger.error(f"MMM.  {attr}  {attr_id}")
        wc_attr_terms = woo_api.get("products/attributes/%s/terms"%attr_id,params={'orderby': 'id', 'order': 'asc', 'per_page': 100})
        _logger.error(f"MMM.wc_attr_terms  {wc_attr_terms}  ")
        _logger.error(f"MMM.wc_attr_terms.json   {wc_attr_terms.json()}")

        if wc_attr_terms.status_code == 200:
            if wc_attr_terms.content:
                attr_terms = wc_attr_terms.json()
                
                for value in attr_terms:
                    _logger.info('\n\n\n\nname: -- %s -- attr id: -- %s \n\n\n\n\n' % (value["name"],attr_id))

                    existing_attr_value = self.env['product.attribute.value'].sudo().search(
                        [('name', '=', value["name"]), ('woocomm_instance_id', '=', wooc_instance.id), ('wooc_id', '=', value["id"])], limit=1)

                    dict_value = {}
                    dict_value['wooc_id'] = value["id"]
                    dict_value['name'] = value["name"]
                    dict_value['wooc_slug'] = value["slug"]
                    dict_value['wooc_description'] = value["description"]
                    dict_value['is_woocomm'] = True
                    dict_value['woocomm_instance_id'] = wooc_instance.id
                    dict_value['attribute_id'] = attr.id
                    dict_value['woocomm_attribute_id'] = attr.id
                    
                    if not existing_attr_value:
                        self.env['product.attribute.value'].sudo().create(dict_value)
                    else:
                        existing_attr_value.sudo().write(dict_value)
                        
                self.env.cr.commit()
                                              
    def export_attribute(self, wooc_instance):
              
        selected_ids = self.env.context.get('active_ids', [])
        attributes_ids = self.sudo().search([('id', 'in', selected_ids), ('woocomm_instance_id', '=', wooc_instance.id)])

        if not attributes_ids:
            raise UserError(_("Please select attributes!!!"))
        
        for attr in attributes_ids:
            try:               
                self.wooc_attribute_create(wooc_instance, attr)
                    
            except Exception as error:
                _logger.info('\n\n\n\n Error message: -- %s \n\n\n\n\n' % error)
                raise UserError(_("Please check your connection and try again"))

    def wooc_attribute_create(self, wooc_instance, attr):
        woo_api = self.init_wc_api(wooc_instance)
        p_attr_exist = self.env['product.attribute'].sudo().search([('id', '=', attr.id), ('woocomm_instance_id', '=', wooc_instance.id)])
        
        if p_attr_exist.wooc_id:
            check_attr  = woo_api.get("products/attributes/%s" %p_attr_exist.wooc_id)
            if check_attr.status_code in [400, 404]:
                p_attr_exist.wooc_id = False
                
        if not p_attr_exist.wooc_id: 
            data = {"name": attr.name,}
            wc_attr_data = woo_api.post("products/attributes", data)
            wc_attr = wc_attr_data.json()
            
            _logger.info('\n\n\n\nwc products attr: %s--\n\n\n\n\n' % wc_attr) 

            if wc_attr_data.status_code == 400:
                if wc_attr["code"] == "woocommerce_rest_cannot_create":
                    wc_attr['id'], wc_attr['slug'] = self.wooc_attribute_check( wooc_instance, str(attr.name))
                else:
                    raise UserError(_(wc_attr["message"]))
            
            p_attr_exist.write({"wooc_id": wc_attr['id'],
                                "woocomm_attr_slug": wc_attr['slug'],
                                "is_woocomm": True,
                                "woocomm_instance_id": wooc_instance.id,})            
            attr_id = wc_attr['id'] 
            self.env.cr.commit()
            
        else : 
            attr_id = p_attr_exist.wooc_id
            
        if attr_id:
            for val in attr.value_ids:
                self.wooc_attribute_terms_create(wooc_instance, p_attr_exist, attr_id, val)
                
            # self.env.cr.commit()
            return attr_id
        
        return False
        
    def wooc_attribute_terms_create(self, wooc_instance, p_attr, attr_wc_id, attr_val):
        
        _logger.info('\n\n\n\nwooc_attribute_terms_create: %s--\n\n\n\n\n' % attr_wc_id) 
        woo_api = self.init_wc_api(wooc_instance)
        attr_val_exist = self.env['product.attribute.value'].sudo().search([('id', '=', attr_val.id), ('woocomm_instance_id', '=', wooc_instance.id)])
        
        term_id = ''
              
        if attr_val_exist.wooc_id:
            check_attr_term  = woo_api.get("products/attributes/%s/terms/%s" %(attr_wc_id, attr_val_exist.wooc_id))
            if check_attr_term.status_code in [400, 404]:
                attr_val_exist.wooc_id = False        
        
        if not attr_val_exist.wooc_id :
            data = {"name": attr_val.name}
            wc_attr_term_data = woo_api.post("products/attributes/%s/terms" %attr_wc_id, data)
            wc_attr_term = wc_attr_term_data.json()
           
            if wc_attr_term_data.status_code == 400:
                if wc_attr_term["code"] == "term_exists":
                    term_id = wc_attr_term["data"]["resource_id"]
        else :
            term_id = attr_val_exist.wooc_id
            
        if  term_id:
            wc_attr_term = woo_api.get("products/attributes/%s/terms/%s" %(attr_wc_id, term_id)).json()
                
        if wc_attr_term['id']:
            term_data = {"wooc_id": wc_attr_term['id'],
                                    "wooc_slug": wc_attr_term['slug'],
                                    "wooc_description": wc_attr_term['description'],
                                    "is_woocomm": True,
                                    "woocomm_instance_id": wooc_instance.id,
                                    "attribute_id": p_attr.id,
                                    "woocomm_attribute_id": p_attr.id,}
            attr_val_exist.write(term_data)
            self.env.cr.commit()
        return
        
    def wooc_attribute_check(self, wooc_instance, check_attr_slug):
        woo_api = self.init_wc_api(wooc_instance)
        attr_lists = woo_api.get("products/attributes/").json()
        for attr in attr_lists:
            if check_attr_slug == attr['name']:
                return attr['id'], attr['slug']
    
    def action_export_product_attribute(self):
        wooc_instance = self.env['woocommerce.instance'].sudo().search([('id', '=', self.woocomm_instance_id.id)])
        return self.export_attribute(wooc_instance)        

class ProductAttributeValue(models.Model):
    _inherit = 'product.attribute.value'
    
    wooc_id = fields.Char(string='WooCommerce Attribute Terms Id')
    wooc_slug = fields.Char(string='WooCommerce Attribute Terms Slug')
    wooc_description = fields.Text(string='WooCommerce Attribute Terms Description')
    
    is_woocomm = fields.Boolean(string='Is WooCommerce?')
    
    woocomm_instance_id = fields.Many2one('woocommerce.instance', string='WooCommerce Instance')
    woocomm_attribute_id = fields.Many2one('product.attribute', 'WooCommerce Attribute', copy=False, required=True, domain="[('woocomm_instance_id', '=', woocomm_instance_id)]")
