# -*- coding: utf-8 -*-
import logging
from odoo.exceptions import UserError
from odoo import models, api, _, fields

_logger = logging.getLogger(__name__)
class WooCommerceResPartnerInstance(models.TransientModel):
    _name = 'woocomm.res.partner.instance.exp'
    _description = 'Customer Export'

    woocomm_instance_id = fields.Many2one('woocommerce.instance')

    def customer_instance_for_exp(self):
        instance_id = self.woocomm_instance_id
        self.env['res.partner'].export_customers(instance_id)
        
    @api.model
    def default_get(self, fields):
        res = super(WooCommerceResPartnerInstance, self).default_get(fields)
        try:
            instance = self.env['woocommerce.instance'].search([])[0]
        except Exception as error:
            raise UserError(_("Please create and configure WooCommerce Instance"))

        if instance:
            res['woocomm_instance_id'] = instance.id

        if self.env['woocommerce.instance']._context.get('woocomm_instance_id'):
            res['woocomm_instance_id'] = self.env['woocommerce.instance']._context.get('woocomm_instance_id')

        return res


class WooCommerceResPartnerInstanceImp(models.TransientModel):
    _name = 'woocomm.res.partner.instance.imp'
    _description = 'Customer Import'

    woocomm_instance_id = fields.Many2one('woocommerce.instance')

    def customer_instance_for_imp(self):
        instance_id = self.woocomm_instance_id
        self.env['res.partner'].import_customer(instance_id)

        
        current_instance = self.env['woocommerce.instance'].sudo().search([('id','=',self.woocomm_instance_id.id)],limit=1)
        customer_action = current_instance.get_customers()
        customer_action['customer_action'].update({'target': "main",})
        return customer_action['customer_action']
  
          
    @api.model
    def default_get(self, fields):
        res = super(WooCommerceResPartnerInstanceImp, self).default_get(fields)
        try:
            instance = self.env['woocommerce.instance'].search([])[0]
        except Exception as error:
            raise UserError(_("\n\n\nPlease create and configure WooCommerce Instance\n\n"))
        
        if instance:
            res['woocomm_instance_id'] = instance.id

        return res

