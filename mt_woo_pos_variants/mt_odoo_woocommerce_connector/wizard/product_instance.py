# -*- coding: utf-8 -*-

from odoo.exceptions import UserError
from odoo import models, _, api, fields
import logging

_logger = logging.getLogger(__name__)
class WooCommerceProductInstanceExp(models.Model):
    _name = 'woocomm.product.instance.exp'
    _description = 'Product Export Instance'

    woocomm_instance_id = fields.Many2one('woocommerce.instance', string="WooCommerce Instance")
    force_update_product = fields.Boolean(string="Force Update Product", default=False)
    force_update_image = fields.Boolean(string="Force Update Image", default=False)

    def product_instance_selected_for_exp(self):

        self.env['product.template'].export_product(self.woocomm_instance_id, self.force_update_product, self.force_update_image)
        return {'type': 'ir.actions.act_window_close'}
        # return self.env['message.wizard'].success("No new Product to Export..!! \nIf trying to export existing product, tick Force Update Product")
        
    @api.model
    def default_get(self, fields):
               
        res = super(WooCommerceProductInstanceExp, self).default_get(fields)
        try:
            instance = self.env['woocommerce.instance'].search([])[0]
        except Exception as error:
            raise UserError(_("Please create and configure WooCommerce Instance"))

        if instance:
            res['woocomm_instance_id'] = instance.id
        
        if self.env['woocommerce.instance']._context.get('woocomm_instance_id'):
            res['woocomm_instance_id'] = self.env['woocommerce.instance']._context.get('woocomm_instance_id')
                          
        return res


class WooCommerceProductInstanceImp(models.Model):
    _name = 'woocomm.product.instance.imp'
    _description = 'Product Import Instance'

    woocomm_instance_id = fields.Many2one('woocommerce.instance')
    is_force_update = fields.Boolean(string="Force Import and Update From WooCommerce", default=False)


    def product_instance_selected_for_imp(self):
        # woocomm_instance_id = self.env['woocommerce.instance'].search([], limit=1, order='id desc')
        self.env['product.template'].import_product(self.woocomm_instance_id, self.is_force_update)
        
        current_instance = self.env['woocommerce.instance'].sudo().search([('id','=',self.woocomm_instance_id.id)],limit=1)
        product_action = current_instance.get_products()
        product_action['product_action'].update({'target': "main",})
        return product_action['product_action']

    @api.model
    def default_get(self, fields):
        res = super(WooCommerceProductInstanceImp, self).default_get(fields)
        try:
            instance = self.env['woocommerce.instance'].search([])[0]
        except Exception as error:
            raise UserError(_("Please create and configure WooCommerce Instance"))

        if instance:
            res['woocomm_instance_id'] = instance.id
  
        return res
