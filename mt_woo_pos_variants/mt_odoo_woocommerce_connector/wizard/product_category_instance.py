# -*- coding: utf-8 -*-

from odoo.exceptions import UserError
from odoo import models, api, _, fields

import logging

_logger = logging.getLogger(__name__)

class WooCommerceProductCategoryInstance(models.TransientModel):
    _name = 'woocomm.product.category.instance.exp'
    _description = 'Product Category Export'

    woocomm_instance_id = fields.Many2one('woocommerce.instance')

    def product_category_instance_for_exp(self):
        instance_id = self.woocomm_instance_id
        self.env['product.category'].wooc_export_category(instance_id)
        
        return {
                'type': 'ir.actions.client',
                'tag': 'reload',
                }

    @api.model
    def default_get(self, fields):
        res = super(WooCommerceProductCategoryInstance, self).default_get(fields)
        try:
            instance = self.env['woocommerce.instance'].search([])[0]
        except Exception as error:
            raise UserError(_("Please create and configure WooCommerce Instance"))

        if instance:
            res['woocomm_instance_id'] = instance.id

        if self.env['woocommerce.instance']._context.get('woocomm_instance_id'):
            res['woocomm_instance_id'] = self.env['woocommerce.instance']._context.get('woocomm_instance_id')
                        
        return res


class WooCommerceProductCategoryInstanceImp(models.Model):
    _name = 'woocomm.product.category.instance.imp'
    _description = 'Product Category Import'

    woocomm_instance_id = fields.Many2one('woocommerce.instance')

    def product_category_instance_for_imp(self):
        instance_id = self.woocomm_instance_id
        self.env['product.category'].import_product_category(instance_id)
        return
    @api.model
    def default_get(self, fields):
        res = super(WooCommerceProductCategoryInstanceImp, self).default_get(fields)
        try:
            instance = self.env['woocommerce.instance'].search([])[0]
        except Exception as error:
            raise UserError(_("Please create and configure WooCommerce Instance"))

        if instance:
            res['woocomm_instance_id'] = instance.id
            
        if self.env['woocommerce.instance']._context.get('woocomm_instance_id'):
            res['woocomm_instance_id'] = self.env['woocommerce.instance']._context.get('woocomm_instance_id')
              
        return res
