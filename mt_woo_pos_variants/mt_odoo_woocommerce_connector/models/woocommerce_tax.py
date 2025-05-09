# -*- coding: utf-8 -*-
import time
import logging

from woocommerce import API
from odoo import models, api, fields, _
from odoo.exceptions import UserError
# from odoo.tools import config
# config['limit_time_real'] = 1000000

_logger = logging.getLogger(__name__)

class Taxes(models.Model):
    _inherit = 'account.tax'

    @api.model
    def default_get(self, fields):
        res = super(Taxes, self).default_get(fields)
        if self.env['woocommerce.instance']._context.get('woocomm_instance_id'):
            res['woocomm_instance_id'] = self.env['woocommerce.instance']._context.get('woocomm_instance_id')
                   
        return res  

    wooc_id = fields.Char('WooCommerce Tax ID')
    wooc_tax_rate = fields.Char('WooCommerce Tax Rate')
    wooc_tax_class = fields.Char('WooCommerce Tax Class')
    
    
    is_exported = fields.Boolean('Synced In WooCommerce', default=False)
    is_woocomm_tax = fields.Boolean('Is WooCommerce Tax', default=False)
    is_shipping = fields.Boolean('Is Shipping', default=True)
    
    woocomm_instance_id = fields.Many2one('woocommerce.instance', ondelete='cascade')
    state_id = fields.Many2one('res.country.state', string='States') 
    
    
    def init_wc_api(self, wooc_instance):
        # wooc_instance = self.env['woocommerce.instance'].search([], limit=1, order='id desc')
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
    
    def get_all_taxes(self, wooc_instance, limit=100):
        woo_api = self.init_wc_api(wooc_instance)
                
        url = "taxes"
        get_next_page = True
        page = 1
        while get_next_page:
            try:
                # _logger.info('\n\n\n\n  page  =  %s \n\n\n\n' % (page) )
                taxes = woo_api.get(url, params={'orderby': 'id', 'order': 'asc','per_page': limit, 'page': page})
                page += 1

            except Exception as error:
                _logger.info('\n\n\n\n  Error Taxes on page=  %s \n\n\n\n' % (page) )
                time.sleep(2)
                continue
            
            if taxes.status_code == 200:
                if taxes.content:
                    parsed_taxes = taxes.json()
                    _logger.info('\n\n\n\n  parsed_taxes  =  %s \n\n\n\n' % (parsed_taxes) )
                    for tax in parsed_taxes:
                        yield tax
                        
                    if len(parsed_taxes) < limit:
                        get_next_page = False 
                else:
                    get_next_page = False 
            else:
                    get_next_page = False 
     
    def import_taxes(self, instance_id):
        for tax in self.get_all_taxes(instance_id):
            self.create_tax(tax, instance_id)

        return      
    
    def create_tax(self, tax_data, wooc_instance):
        
                existing_tax_data = self.env['account.tax'].sudo().search(
                    [('wooc_id', '=', tax_data["id"])], limit=1)
                
                if not existing_tax_data:
                    existing_name_tax_data = self.env['account.tax'].sudo().search(
                        [('name', '=', tax_data["name"]), ('company_id', '=', wooc_instance.wooc_company_id.id)], limit=1)
                    
                    if (existing_name_tax_data):
                        _logger.info('\n\n\n\n  Tax Name Exist =  %s \n\n\n\n' % (tax_data["name"]) )
                        existing_tax_data = existing_name_tax_data
                        # return

                dict_tax = {}
                dict_tax['wooc_id'] = tax_data["id"]
                dict_tax['name'] = tax_data["name"]
                dict_tax['amount'] = float(tax_data['rate'])
                dict_tax['wooc_tax_rate'] = tax_data["rate"]
                dict_tax['wooc_tax_class'] = tax_data["class"]
                dict_tax['description'] = tax_data["name"] + ' ' + str(float(tax_data['rate'])) + '%'
                dict_tax['invoice_label'] = tax_data["name"] + ' ' + str(float(tax_data['rate'])) + '%'
                dict_tax['company_id'] = wooc_instance.wooc_company_id.id
                dict_tax['country_id'] = wooc_instance.wooc_company_id.country_id.id
                dict_tax['is_exported'] = True
                dict_tax['is_woocomm_tax'] = True
                dict_tax['is_shipping'] = tax_data["shipping"]
                dict_tax['woocomm_instance_id'] = wooc_instance.id

                if not existing_tax_data:
                    existing_tax_data = self.env['account.tax'].sudo().create(dict_tax)
                else:
                    existing_tax_data.sudo().write(dict_tax)
            
                self.env.cr.commit()    
                
                return existing_tax_data
     
    def get_wooc_tax(self, tax_id, wooc_instance):
        woo_api = self.init_wc_api(wooc_instance)
        wc_tax_data = woo_api.get("taxes/%s"%tax_id,)
        
        if wc_tax_data.status_code == 200:
            if wc_tax_data.content:
                tax_data = wc_tax_data.json()
                return tax_data
        
        return False

    def wooc_export_taxes(self, wooc_instance):
        woo_api = self.init_wc_api(wooc_instance)
              
        selected_ids = self.env.context.get('active_ids', [])
        tax_ids = self.sudo().search([('id', 'in', selected_ids), ('woocomm_instance_id', '=', wooc_instance.id)])

        if not tax_ids:
            raise UserError(_("Please select taxes!!!"))
        
        for tax in tax_ids:
                                  
            data =  {
                        "country": tax.country_id.code,
                        "state": tax.state_id.code or "",
                        "cities": [],
                        "postcodes": [],
                        "rate": str(tax.amount),
                        "name": tax.name,
                        "shipping": tax.is_shipping
                    }
            _logger.info('\n\n\n\n  wooc_export_taxes =  %s \n\n\n\n' % (data) )
        
                       
            try:               
                if tax.wooc_id:
                    result = woo_api.put("taxes/%s" %tax.wooc_id, data)
                    if result.status_code in [400, 404]:
                        result = woo_api.post("taxes", data)
                    
                    result = result.json() 
                    _logger.info('\n\n\n\n  update result wooc_export_taxes=  %s \n\n\n\n' % (result) )
                else:
                    result = woo_api.post("taxes", data).json()
                    _logger.info('\n\n\n\n  result wooc_export_taxes=  %s \n\n\n\n' % (result) )
                    
                if result:
                    tax.wooc_id = result['id']
                    tax.name = result['name']
                    tax.amount = float(result['rate'])
                    tax.wooc_tax_rate = result["rate"]
                    tax.wooc_tax_class = result["class"]
                    tax.description = tax.description if tax.description else  result["name"] + ' ' + str(float(result['rate'])) + '%' 
                    tax.is_exported = True
                    tax.is_woocomm_tax = True
                    tax.is_shipping = result["shipping"]
                    tax.woocomm_instance_id = wooc_instance.id
                                       
                    self.env.cr.commit()
                               
                _logger.info("\n\n\nTaxes created/updated successfully\n\n")
                # _logger.info("\n\n\nProduct data %s\n\n" % result)
                    
            except Exception as error:
                _logger.info("Tax creation/updation Failed")
                _logger.info('\n\n\n\n Error message: -- %s \n\n\n\n\n' % error)
                raise UserError(_("Please check your connection and try again"))
                  