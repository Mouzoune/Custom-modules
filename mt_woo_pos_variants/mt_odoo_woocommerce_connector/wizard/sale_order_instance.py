# -*- coding: utf-8 -*-

from odoo.exceptions import UserError
from odoo import models, api, _, fields

import logging

_logger = logging.getLogger(__name__)

class WooCommerceSaleOrderInstance(models.TransientModel):
    _name = 'woocomm.sale.order.instance.exp'
    _description = 'Sales Order Export'

    woocomm_instance_id = fields.Many2one('woocommerce.instance')

    def sale_order_instance_for_exp(self):
        instance_id = self.woocomm_instance_id
        self.env['sale.order'].export_selected_so(instance_id)
        
        return {
                'type': 'ir.actions.client',
                'tag': 'reload',
                }

    @api.model
    def default_get(self, fields):
        res = super(WooCommerceSaleOrderInstance, self).default_get(fields)
        try:
            instance = self.env['woocommerce.instance'].search([])[0]
        except Exception as error:
            raise UserError(_("Please create and configure WooCommerce Instance"))

        if instance:
            res['woocomm_instance_id'] = instance.id

        if self.env['woocommerce.instance']._context.get('woocomm_instance_id'):
            res['woocomm_instance_id'] = self.env['woocommerce.instance']._context.get('woocomm_instance_id')
                        
        return res


class WooCommerceSaleOrderInstanceImp(models.Model):
    _name = 'woocomm.sale.order.instance.imp'
    _description = 'Sales Order Import'

    woocomm_instance_id = fields.Many2one('woocommerce.instance')
    is_force_update = fields.Boolean(string="Force Import From WooCommerce", default=False)

    def sale_order_instance_for_imp(self):
        instance_id = self.env['woocommerce.instance'].search([], limit=1, order='id desc')
        self.env['sale.order'].import_sale_order(instance_id, self.is_force_update)

        current_instance = self.env['woocommerce.instance'].sudo().search([('id','=',self.woocomm_instance_id.id)],limit=1)
        #order_action = instance_id.get_total_orders()
        #return order_action['order_action']
        return self.env['sale.order'].sudo().import_sale_order(current_instance, is_force_update=True, from_method='cron')


    @api.model
    def default_get(self, fields):
        res = super(WooCommerceSaleOrderInstanceImp, self).default_get(fields)
        try:
            instance = self.env['woocommerce.instance'].search([])[0]
        except Exception as error:
            raise UserError(_("Please create and configure WooCommerce Instance"))

        if instance:
            res['woocomm_instance_id'] = instance.id
            
        if self.env['woocommerce.instance']._context.get('woocomm_instance_id'):
            res['woocomm_instance_id'] = self.env['woocommerce.instance']._context.get('woocomm_instance_id')
              
        return res
