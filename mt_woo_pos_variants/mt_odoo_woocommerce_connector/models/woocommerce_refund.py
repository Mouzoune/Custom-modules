# -*- coding: utf-8 -*-

import time
import logging

from woocommerce import API
from odoo import fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    wooc_id = fields.Char('WooCommerce Refund ID')
    
    is_exported = fields.Boolean('Synced In WooCommerce', default=False)
    is_refund = fields.Boolean('Is refunded', default=False)
    
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
            
    def action_fail_refund_button(self, message):
        return self.env['message.wizard'].fail(message)
    
    def action_generate_refund_account_move(self):
        action = self.env.ref("mt_odoo_woocommerce_connector.action_woocomm_wizard_generate_refund").read()[0]
        action.update({
            'context': "{'woocomm_instance_id': " + str(self.woocomm_instance_id.id) + "}",
        })        
        return action    
    
    def credit_invoice_refund_create(self, instance_id):
        
        selected_ids = self.env.context.get('active_ids', [])
        order_ids = self.sudo().search([('id', 'in', selected_ids), ('woocomm_instance_id', '=', instance_id.id)])

        if not order_ids:
            raise UserError(_("Please select Orders!!!"))
        
        for order in order_ids: 
            self.woocomm_refund(instance_id, order)
            
    def woocomm_refund(self, wooc_instance, r_invoice):
        
        woo_api = self.init_wc_api(wooc_instance)
        
        data = {}        

        data['line_items'] = []
        so_order = self.env['sale.order'].sudo().search([('name', '=', r_invoice.invoice_origin), ('woocomm_instance_id', '=', wooc_instance.id)], limit=1)
        
        if not so_order.wooc_id:
            so_order = self.env['sale.order'].sudo().search([('invoice_ids', 'in', [r_invoice.id]), ('woocomm_instance_id', '=', wooc_instance.id)], limit=1)

        data.update( {'reason' : "refund from odoo", "api_refund" : False})
        
        so_lines = self.env['sale.order.line'].sudo().search([('order_id', '=', so_order.id), ('woocomm_instance_id', '=', wooc_instance.id)])
        for line in so_lines:
                       
            for id in r_invoice.invoice_line_ids:
                if line.product_id.id ==  id.product_id.id and id.quantity !=0 and not line.is_delivery:
                    line_items = {
                        "id": line.woocomm_so_line_id,
                        "quantity": int(id.quantity),
                        "refund_total": id.price_subtotal,
                        "refund_tax": []
                    }
                    line_items['refund_tax'].append({"id": "1", "refund_total": line.price_tax*(int(id.quantity)/int(line.product_uom_qty)) })                           
                    data['line_items'].append(line_items)
                    break
                
                
                if line.product_id.id ==  id.product_id.id and id.quantity !=0 and line.is_delivery:
                    
                    tax_items = {"id": line.woocomm_so_line_id, "refund_total": line.price_subtotal, 'refund_tax' : []}
                    tax_items['refund_tax'].append({"id": "1", "refund_total": line.price_tax })
                    data['line_items'].append(tax_items) 
                    break
                                                                             
        try:
            
            wc_refund = woo_api.post("orders/%s/refunds"%so_order.wooc_id, data)
            
            _logger.info('\n\n\n\n Result Refund Array   =  %s \n\n\n\n' % (wc_refund.json()) )  
            
            if wc_refund.status_code == 201:
                if wc_refund.content:
                    refund = wc_refund.json()
                    
                    r_invoice.update( {'wooc_id' : refund['id'], 'is_refund' : True,})           
            
        
        except Exception as error:
            _logger.info('\n\n\n\n  Error   =  %s \n\n\n\n' % (error) )
            raise UserError(_(error.response.body))
        
