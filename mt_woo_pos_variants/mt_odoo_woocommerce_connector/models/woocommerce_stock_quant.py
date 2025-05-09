# -*- coding: utf-8 -*-

import logging

from woocommerce import API
from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class WooCommerceProductChangeQuantity(models.TransientModel):
    _inherit = "stock.change.product.qty"
    
    def init_wc_api(self, wooc_instance):
        # wooc_instance = self.env['woocommerce.instance'].search([], limit=1, order='id desc')
        # wooc_instance = self.product_id.woocomm_instance_id
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
    
    def change_product_qty(self):

        super(WooCommerceProductChangeQuantity, self).change_product_qty()

        if self.product_id.wooc_id:
            woocomm_instance_id = self.product_id.woocomm_instance_id if self.product_id.woocomm_instance_id else self.product_id.product_tmpl_id.woocomm_instance_id
            woo_api = self.init_wc_api(woocomm_instance_id)
            p_type = self.product_id.product_tmpl_id.woocomm_product_type
            var_quant_data = {"stock_quantity": self.new_quantity, "manage_stock" : True }      
                  
            if p_type == "variable":
                stock_quantity_update = woo_api.put("products/%s/variations/%s" % (str(self.product_id.wooc_id), str(self.product_id.woocomm_variant_id)), var_quant_data)
                
                result = stock_quantity_update.json()

                wooc_variant = self.env['woocommerce.product.variant'].sudo().search([('wooc_id', '=', self.product_id.woocomm_variant_id), ('woocomm_instance_id', '=', self.product_id.woocomm_instance_id.id)])
                data = {"wooc_stock_quantity" : result["stock_quantity"], "is_manage_stock" : result["manage_stock"]}
                if wooc_variant:
                    wooc_variant.write(data)
                    self.env.cr.commit()

            elif p_type == "simple":
                stock_quantity_update = woo_api.put("products/%s"% (str(self.product_id.wooc_id)), var_quant_data)       

        return {'type': 'ir.actions.act_window_close'}
    


    def change_product_quantities(self):
        for rec in self.env['stock.quant'].search([('location_id', '=', 8)]).filtered(lambda x: x.available_quantity > 0):
#            _logger.error(f'rec {rec.display_name}')
            if rec.product_id.wooc_id and rec.available_quantity > 0:
                _logger.error(f'rec {rec.display_name} wooId: {rec.product_id.wooc_id} Qty:  {rec.available_quantity}')

                woocomm_instance_id = rec.product_id.woocomm_instance_id if rec.product_id.woocomm_instance_id else rec.product_id.product_tmpl_id.woocomm_instance_id
                woo_api = self.init_wc_api(woocomm_instance_id)
                p_type = rec.product_id.product_tmpl_id.woocomm_product_type
                var_quant_data = {"stock_quantity": rec.available_quantity, "manage_stock": True}

                if p_type == "variable":
                    stock_quantity_update = woo_api.put("products/%s/variations/%s" % (
                    str(rec.product_id.wooc_id), str(rec.product_id.woocomm_variant_id)), var_quant_data)

                    result = stock_quantity_update.json()
                    _logger.error(f'result {result}')
                    wooc_variant = self.env['woocommerce.product.variant'].sudo().search(
                        [('wooc_id', '=', rec.product_id.woocomm_variant_id)])
                    if result.get("stock_quantity", False):
                        data = {"wooc_stock_quantity": result["stock_quantity"], "is_manage_stock": result["manage_stock"]}
                        if wooc_variant:
                            wooc_variant.write(data)
                            self.env.cr.commit()

                elif p_type == "simple":
                    stock_quantity_update = woo_api.put("products/%s" % (str(rec.product_id.wooc_id)), var_quant_data)
