# -*- coding: utf-8 -*-

from odoo.exceptions import UserError
from odoo import models, api, _, fields
import logging

_logger = logging.getLogger(__name__)
class WooCommerceOrderAction(models.TransientModel):
    _name = 'woocomm.order.actions.wizard'
    _description = 'WooCommerce Order Actions'
    
   
    @api.model
    def default_get(self, fields):
     
        res = super(WooCommerceOrderAction, self).default_get(fields)      
      
        try:
            instance = self.env['woocommerce.instance'].search([])[0]
        except Exception as error:
            raise UserError(_("Please create and configure WooCommerce Instance"))

        if instance:
            res['woocomm_instance_id'] = instance.id

        if self.env['woocommerce.instance']._context.get('woocomm_instance_id'):
            res['woocomm_instance_id'] = self.env['woocommerce.instance']._context.get('woocomm_instance_id')
       
        selected_ids = self.env['sale.order']._context.get('active_ids', [])
        
        res['order_action_status'] = self._compute_order_action_status(selected_ids)

        return res    
    
    

    def _get_selection_normal(self):
        return [('cancel', "Cancel Order"), ('refund', "Full Refund Order"), ('info_update', "Order Info Import"),]
        
    def _get_selection_new_order(self):
        return [('new_order', "Create New Order"),]
    
    def _get_selection_order_payment(self):
        return [('set_paid', "Set Order as Paid"), ('info_update', "Order Info Import")]
    
    def _get_selection_info_update(self):
        return [('info_update', "Order Info Import")]
       
    def _get_selection_payment_complete(self):
        return [('refund', "Full Refund Order"), ('cancel', "Cancel Order"), ('info_update', "Order Info Import")]
    
    def _get_selection_order_complete(self):
        return [('refund', "Full Refund Order"), ('info_update', "Order Info Import")]
    
    
    woocomm_instance_id = fields.Many2one('woocommerce.instance')
    current_order_id = fields.Char(compute='_compute_current_order_id', store=True, precompute=True)
    order_action_status = fields.Char()
    
    order_actions = fields.Selection(_get_selection_normal, string="Order Actions") 
    order_actions_new_order = fields.Selection(_get_selection_new_order, string="Order Actions") 
    order_actions_order_payment = fields.Selection(_get_selection_order_payment, string="Order Actions") 
    order_actions_info_update = fields.Selection(_get_selection_info_update, string="Order Actions") 
    order_actions_payment_complete = fields.Selection(_get_selection_payment_complete, string="Order Actions") 
    order_actions_order_complete = fields.Selection(_get_selection_order_complete, string="Order Actions") 
         
        
        
    @api.depends("woocomm_instance_id")
    def _compute_current_order_id(self):
        for rec in self:
            rec.current_order_id = self.env.context.get('order_actions')
            
    def _compute_order_action_status(self, selected_ids):

        order_id = self.env['sale.order'].sudo().search([('id', 'in', selected_ids)])

        if order_id:      
            if not order_id.wooc_id:
                return "new_order"
                       
            if order_id.wooc_id:
                
                if order_id.woocomm_status in ('pending', 'on-hold'):
                    return "order_payment"  
                
                if order_id.woocomm_status in ('cancelled', 'failed', 'trash'):
                    return "info_update"                    
                                        
                if order_id.woocomm_status in ('processing', 'refunded'):
                    return "payment_complete"
                
                if order_id.woocomm_status in ('completed'):
                    return "order_complete" 
                         
            
        return "default"
                
    
    def woocomm_action(self):
        order_actions = ""

        if self.order_actions:
            order_actions = self.order_actions
        if self.order_actions_new_order:
            order_actions = self.order_actions_new_order
        if self.order_actions_order_payment:
            order_actions = self.order_actions_order_payment
        if self.order_actions_info_update:
            order_actions = self.order_actions_info_update
        if self.order_actions_payment_complete:
            order_actions = self.order_actions_payment_complete
        if self.order_actions_order_complete:
            order_actions = self.order_actions_order_complete
        
        instance_id = self.woocomm_instance_id
        if order_actions == "new_order":
            self.env['sale.order'].woocomm_new_orders(instance_id)   
        if order_actions == "set_paid":
            self.env['sale.order'].woocomm_set_paid(instance_id)                             
        if order_actions == "cancel":         
            self.env['sale.order'].woocomm_order_cancel(instance_id)
        if order_actions == "refund":             
            self.env['sale.order'].order_refund_create(instance_id)
        if order_actions == "info_update":             
            self.env['sale.order'].woocomm_force_info_update(instance_id)
                    
        return {
                'type': 'ir.actions.client',
                'tag': 'reload',
                }


