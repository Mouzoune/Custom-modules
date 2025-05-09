# -*- coding: utf-8 -*-

from odoo.exceptions import UserError
from odoo import models, _, api, fields
import logging

_logger = logging.getLogger(__name__)
class WooCommerceStockQuantExp(models.Model):
    _name = 'woocomm.product.stock.quant.exp'
    _description = 'Product Stock Instance'

    woocomm_instance_id = fields.Many2one('woocommerce.instance', string="WooCommerce Instance")

    def product_stock_quantity_exp(self):

        self.env['product.template'].woocomm_product_quantity_update(self.woocomm_instance_id)
        
    @api.model
    def default_get(self, fields):
               
        res = super(WooCommerceStockQuantExp, self).default_get(fields)
        try:
            instance = self.env['woocommerce.instance'].search([])[0]
        except Exception as error:
            raise UserError(_("Please create and configure WooCommerce Instance"))

        if instance:
            res['woocomm_instance_id'] = instance.id
        
        if self.env['woocommerce.instance']._context.get('woocomm_instance_id'):
            res['woocomm_instance_id'] = self.env['woocommerce.instance']._context.get('woocomm_instance_id')
                          
        return res
