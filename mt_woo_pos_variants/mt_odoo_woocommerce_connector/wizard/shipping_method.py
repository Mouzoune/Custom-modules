# -*- coding: utf-8 -*-
import logging
from odoo.exceptions import UserError
from odoo import models, api, _, fields

_logger = logging.getLogger(__name__)

class WooCommerceDeliveryCarrierWizardImp(models.TransientModel):
    _name = 'woocomm.delivery.carrier.wizard.imp'
    _description = 'Shipping methods Import'

    woocomm_instance_id = fields.Many2one('woocommerce.instance')

    def shipping_methods_view(self):
        view = self.env.ref('delivery.view_delivery_carrier_tree').read()[0]
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Shipping Methods',
            'domain': [('woocomm_instance_id', '=', self.woocomm_instance_id.id)],
            'res_model': 'delivery.carrier',
            'view_id': view.get('view_id')[0] if view.get('view_id') else False,
            'view_mode': 'tree',
            'target': 'current',
        }     
        
    def shipping_methods_imp(self):
        instance_id = self.woocomm_instance_id
        self.env['delivery.carrier'].import_shipping_method(instance_id)
  
    @api.model
    def default_get(self, fields):
        res = super(WooCommerceDeliveryCarrierWizardImp, self).default_get(fields)
        try:
            instance = self.env['woocommerce.instance'].search([])[0]
        except Exception as error:
            raise UserError(_("\n\n\nPlease create and configure WooCommerce Instance\n\n"))
        
        if instance:
            res['woocomm_instance_id'] = instance.id

        return res

