# -*- coding: utf-8 -*-

from odoo.exceptions import UserError
from odoo import models, api, _, fields

import logging

_logger = logging.getLogger(__name__)

class WooCommerceTaxInstance(models.TransientModel):
    _name = 'woocomm.account.tax.instance.exp'
    _description = 'Tax Export'

    woocomm_instance_id = fields.Many2one('woocommerce.instance')

    def tax_instance_for_exp(self):
        instance_id = self.woocomm_instance_id
        self.env['account.tax'].wooc_export_taxes(instance_id)
        
        return {
                'type': 'ir.actions.client',
                'tag': 'reload',
                }

    @api.model
    def default_get(self, fields):
        res = super(WooCommerceTaxInstance, self).default_get(fields)
        try:
            instance = self.env['woocommerce.instance'].search([])[0]
        except Exception as error:
            raise UserError(_("Please create and configure WooCommerce Instance"))

        if instance:
            res['woocomm_instance_id'] = instance.id

        if self.env['woocommerce.instance']._context.get('woocomm_instance_id'):
            res['woocomm_instance_id'] = self.env['woocommerce.instance']._context.get('woocomm_instance_id')
                        
        return res


class WooCommerceTaxInstanceImp(models.Model):
    _name = 'woocomm.account.tax.instance.imp'
    _description = 'Tax Import'

    woocomm_instance_id = fields.Many2one('woocommerce.instance')

    def tax_instance_for_imp(self):
        instance_id = self.woocomm_instance_id
        self.env['account.tax'].import_taxes(instance_id)
        return

    @api.model
    def default_get(self, fields):
        res = super(WooCommerceTaxInstanceImp, self).default_get(fields)
        try:
            instance = self.env['woocommerce.instance'].search([])[0]
        except Exception as error:
            raise UserError(_("Please create and configure WooCommerce Instance"))

        if instance:
            res['woocomm_instance_id'] = instance.id
            
        if self.env['woocommerce.instance']._context.get('woocomm_instance_id'):
            res['woocomm_instance_id'] = self.env['woocommerce.instance']._context.get('woocomm_instance_id')
              
        return res
