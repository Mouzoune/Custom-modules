# -*- coding: utf-8 -*-

from odoo.exceptions import UserError
from odoo import models, api, _, fields


class GenerateInvoice(models.TransientModel):
    _name = 'woocomm.generate.invoice'
    _description = 'Invoice generate'

    woocomm_instance_id = fields.Many2one('woocommerce.instance')

    def generate_invoice(self):
        instance_id = self.woocomm_instance_id
        self.env['sale.order'].order_generate_invoice(instance_id)
        
        return {
                'type': 'ir.actions.client',
                'tag': 'reload',
                }

    @api.model
    def default_get(self, fields):
        res = super(GenerateInvoice, self).default_get(fields)
        try:
            instance = self.env['woocommerce.instance'].search([])[0]
        except Exception as error:
            raise UserError(_("Please create and configure WooCommerce Instance"))

        if instance:
            res['woocomm_instance_id'] = instance.id
            
        if self.env['woocommerce.instance']._context.get('woocomm_instance_id'):
            res['woocomm_instance_id'] = self.env['woocommerce.instance']._context.get('woocomm_instance_id')
         
        return res
