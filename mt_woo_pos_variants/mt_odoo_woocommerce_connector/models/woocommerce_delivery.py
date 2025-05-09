# -*- coding: utf-8 -*-
import logging

from woocommerce import API
from odoo import fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    wooc_id = fields.Char('WooCommerce ID')
    woocomm_method_id = fields.Char('WooCommerce Method Id')
    
    is_woocomm = fields.Boolean('Synced In WooCommerce', default=False)
    
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
            
    def import_shipping_method(self, instance_id):
        woo_api = self.init_wc_api(instance_id)
        shipping_methods = woo_api.get("shipping_methods").json()
        for shipping in shipping_methods:
            self.create_shipping_method(instance_id, shipping)

    
    def create_shipping_method(self, instance_id, shipping_method):
        shipping = self.sudo().search([('woocomm_method_id', '=', shipping_method['id']), ('woocomm_instance_id', '=', instance_id.id)], limit=1)
        if not shipping:
            _logger.info('\n\n\n\n create_shipping_method \n\n\n\n\n')
            delivery_product = self.env['product.product'].sudo().create({
                'name': shipping_method['title'],
                'detailed_type': 'service',
                'taxes_id': [(6, 0, [])]
            })
                            
            vals = {
                'name': shipping_method['title'],
                'product_id': delivery_product.id,
                'woocomm_method_id' : shipping_method['id'],
                'fixed_price': float(0),
                'is_woocomm': True,
                'woocomm_instance_id': instance_id.id,                    
            }
            shp_mthd = self.sudo().create(vals)
        self.env.cr.commit()
            
    
