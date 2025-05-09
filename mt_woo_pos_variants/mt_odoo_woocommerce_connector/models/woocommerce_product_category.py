# -*- coding: utf-8 -*-
import time
import logging

from woocommerce import API
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import config
config['limit_time_real'] = 1000000

_logger = logging.getLogger(__name__)

class ProductCategory(models.Model):
    _inherit = "product.category"
    _order = 'wooc_id'
    
    @api.model
    def default_get(self, fields):
        res = super(ProductCategory, self).default_get(fields)
        if self.env['woocommerce.instance']._context.get('woocomm_instance_id'):
            res['woocomm_instance_id'] = self.env['woocommerce.instance']._context.get('woocomm_instance_id')
            res['is_woocomm_category'] = True
        return res
    
    wooc_id = fields.Char('WooCommerce ID')
    wooc_parent_id = fields.Char('WooCommerce Parent ID')
    wooc_cat_slug = fields.Char('Slug')
    wooc_cat_description = fields.Html(string="Category Description",translate=True)    
    
    is_woocomm_category = fields.Boolean(string='Is WooCommerce Category?')
    is_exported = fields.Boolean('Synced In WooCommerce', default=False)
    
    woocomm_instance_id = fields.Many2one('woocommerce.instance', ondelete='cascade')
    
    
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

    def get_all_product_category(self, wooc_instance, limit=100):
        woo_api = self.init_wc_api(wooc_instance)
                
        url = "products/categories"
        get_next_page = True
        page = 1
        while get_next_page:
            try:
                # _logger.info('\n\n\n\n  page  =  %s \n\n\n\n' % (page) )
                product_category = woo_api.get(url, params={'orderby': 'id', 'order': 'asc','per_page': limit, 'page': page})
                page += 1

            except Exception as error:
                _logger.info('\n\n\n\n  Error product_category on page=  %s \n\n\n\n' % (page) )
                time.sleep(2)
                continue
            
            if product_category.status_code == 200:
                if product_category.content:
                    parsed_product_category = product_category.json()
                    _logger.info('\n\n\n\n  parsed_product_category  =  %s \n\n\n\n' % (parsed_product_category) )
                    for category in parsed_product_category:
                        yield category
                        
                    if len(parsed_product_category) < limit:
                        get_next_page = False 
                else:
                    get_next_page = False 
            else:
                    get_next_page = False 

    def import_product_category(self, instance_id):
        for category in self.get_all_product_category(instance_id):
            if category:
                self.create_category(category, instance_id)

        return      

    def create_category(self, category_data, wooc_instance):
                
                dict_cat = {}
                _logger.error(category_data)
                
                existing_category_data = self.env['product.category'].sudo().search(
                    [('wooc_id', '=', category_data["id"]), ('woocomm_instance_id', '=', wooc_instance.id)], limit=1)
                
                if category_data.get('parent') and not existing_category_data.wooc_parent_id:
                    
                    existing_parent_cat = self.env['product.category'].sudo().search(
                    [('wooc_id', '=', category_data["parent"]), ('woocomm_instance_id', '=', wooc_instance.id)], limit=1)
                     
                    if not existing_parent_cat:
                        parent_categ = self.get_wooc_category(category_data["parent"], wooc_instance)
                        if parent_categ:
                            existing_parent_cat = self.create_category(parent_categ, wooc_instance)
                        
                    dict_cat['parent_id'] = existing_parent_cat.id

                
                dict_cat['wooc_id'] = category_data.get('id')
                dict_cat['wooc_parent_id'] = category_data.get('parent')
                dict_cat['name'] = category_data.get('name')
                dict_cat['wooc_cat_slug'] = category_data.get('slug')
                dict_cat['wooc_cat_description'] = category_data['description'] if category_data.get('description') else ''
                dict_cat['is_woocomm_category'] = True
                dict_cat['is_exported'] = True
                dict_cat['woocomm_instance_id'] = wooc_instance.id

                
                if not existing_category_data:
                    existing_category_data = self.env['product.category'].sudo().create(dict_cat)
                else:
                    existing_category_data.sudo().write(dict_cat)
            
                self.env.cr.commit()    
                
                return existing_category_data

    def get_wooc_category(self, category_id, wooc_instance):
        woo_api = self.init_wc_api(wooc_instance)
        wc_category_data = woo_api.get("product/categories/%s"%category_id,)
        
        if wc_category_data.status_code == 200:
            if wc_category_data.content:
                category_data = wc_category_data.json()
                return category_data
        
        return False

    def wooc_export_category(self, wooc_instance):
                      
        selected_ids = self.env.context.get('active_ids', [])
        category_ids = self.sudo().search([('id', 'in', selected_ids), ('woocomm_instance_id', '=', wooc_instance.id)])

        if not category_ids:
            raise UserError(_("Please select category!!!"))
        
        for category in category_ids:
            try: 
                self.wooc_export_create_category(category, wooc_instance)
                
            except Exception as error:
                _logger.info("Category creation/updation Failed")
        
        _logger.info("\n\n\nCategory created/updated successfully\n\n")

    def wooc_export_create_category(self, category, wooc_instance):
        
        woo_api = self.init_wc_api(wooc_instance)    
                                
        data =  {
                    "name": category.name,
                    "slug": category.wooc_cat_slug if category.wooc_cat_slug else "",
                    "description": category.wooc_cat_description,
                    "display": "default",
                }
        
        if category.parent_id:
            if not category.parent_id.wooc_parent_id:
                self.wooc_export_create_category(category.parent_id, wooc_instance)
                
            data.update({"parent": category.parent_id.wooc_id})
        else :
            data.update({"parent": 0})
            
        _logger.info('\n\n\n\n  wooc_export_category =  %s \n\n\n\n' % (data) ) 
                    
        try:               
            if category.wooc_id:
                result = woo_api.put("products/categories/%s" %category.wooc_id, data)
                
                if result.status_code in [400, 404]:
                    result = woo_api.post("products/categories", data)
                    
                result = result.json()
                _logger.info('\n\n\n\n  update result wooc_export_category=  %s \n\n\n\n' % (result) )
            else:
                result = woo_api.post("products/categories", data).json()
                _logger.info('\n\n\n\n  result wooc_export_category=  %s \n\n\n\n' % (result) )
                
            if result:
                category.wooc_id = result['id']
                category.name = result['name']
                category.wooc_parent_id = result['parent']
                category.wooc_cat_slug = result["slug"]
                category.wooc_cat_description = result['description'] if result.get('description') else ''
                category.is_exported = True
                category.is_woocomm_category = True
                category.woocomm_instance_id = wooc_instance.id                          
                                    
                self.env.cr.commit()
                                                            
        except Exception as error:
            _logger.info('\n\n\n\n Error message: -- %s \n\n\n\n\n' % error)               
            raise UserError(_("Please check your connection and try again"))

