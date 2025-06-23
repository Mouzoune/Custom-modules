# -*- coding: utf-8 -*-

import time
import logging

from woocommerce import API
from odoo.exceptions import UserError

from odoo import api, fields, _, models
from datetime import datetime
from odoo.tools import config

_logger = logging.getLogger(__name__)
def connect_to_wc():
    wcapi = API(url="http://wordpress", port=80, consumer_key="ck_2439afce161648a06716221963ba3ec66ee5f4c5", consumer_secret="cs_78791227a9d1f2555152e89ca0769d5ebc28cd77", wp_api=True, version="wc/v3")
    return wcapi
# wcapi = API(url="https://odoo.nstore.ma", port=80, consumer_key="ck_d3ab1d563397dbaf337ac054af32e7ab97db957f", consumer_secret="cs_9709ed568304a0fe2b4d4e328d8e7a67be7d1ec0", wp_api=True, version="wc/v3")



class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    @api.model
    def default_get(self, fields):
        res = super(SaleOrder, self).default_get(fields)
        if self.env['woocommerce.instance']._context.get('woocomm_instance_id'):
            res['woocomm_instance_id'] = self.env['woocommerce.instance']._context.get('woocomm_instance_id')
            
        return res

    wooc_id = fields.Char('WooCommerce ID')
    woocomm_order_no = fields.Char('WooCommerce Order No.')
    woocomm_payment_method = fields.Char("WooCommerce Payment Method")
    woocomm_status = fields.Selection([
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('on-hold', 'On Hold'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
        ('failed', 'Failed'),
        ('trash', 'Trash')], string="WooCommerce Order Status")
    woocomm_product_status = fields.Selection([
        ('new_order', 'طلب جديد'),
        ('confirmed', 'تم التأكد '),
        ('ready_for_shipping', 'جاهز للشحن'),
        ('in_shipping', 'قيد الشحن'),
        ('dispatched', 'تم الإرسال'),
        ('delivered', 'تم التسليم'),
        ('returned', 'تم الاسترجاع'),
        ('paid', 'تم الدفع'),
        ('refunded', 'إعادة الأموال'),
        ('no_response_to_call', 'عدم الإستجابة للإتصال'),
        ('exchange', 'تبديل'),
        ('sent_for_repair', 'الإرسال للإصلاح'),
        ('damaged', 'تلف'),
        ('failed', 'فشل')], string="Product status")

    woocomm_order_date = fields.Date(string="WooCommerce Order Date")
    woocomm_order_subtotal = fields.Float('WooCommerce Order Subtotal')
    woocomm_order_total_tax = fields.Float('WooCommerce Order Total Tax')
    woocomm_order_total = fields.Float('WooCommerce Order Total Price')
    woocomm_order_note = fields.Char('WooCommerce Order Note from Customer')
    woocomm_customer_id = fields.Char('WooCommerce Customer Id.')
    
    is_exported = fields.Boolean('Synced In WooCommerce', default=False)
    is_woocomm_order = fields.Boolean('Is WooCommerce Order', default=False)
    
#    woocomm_instance_id = fields.Many2one('woocommerce.instance', ondelete='cascade')

    woocomm_instance_id = fields.Many2one('woocommerce.instance', ondelete='cascade') 

    partner_phone = fields.Char(compute='_get_partner_phone', string='Phone')
    woocommerce_tag_ids = fields.Many2many('sale.order.tags.woocommerce', string='Tags')
    partner_name_and_wooc_id_concatenated = fields.Char(compute='_get_partner_name_wooc_id_concatenated')
    partner_city_street_wooc_id_concatenated = fields.Char(compute='_get_partner_name_wooc_id_concatenated', string="Adresse complète")

    def _get_partner_name_wooc_id_concatenated(self):
        for rec in self:
            rec.partner_name_and_wooc_id_concatenated = f'{rec.partner_id.display_name} {rec.wooc_id}'
            rec.partner_city_street_wooc_id_concatenated = (f'{rec.partner_id.city}: {rec.partner_id.street if rec.partner_id.street else ""}'
                                                            f' {rec.partner_id.street2 if rec.partner_id.street2 else ""} '
                                                            f'{rec.partner_id.zip if rec.partner_id.zip else ""}')


    @api.depends('partner_id.child_ids', 'partner_id.child_ids.phone')
    def _get_partner_phone(self):
        for rec in self:
            rec.partner_phone = rec.partner_id.phone if rec.partner_id.phone else ' - '.join(set(rec.partner_id.mapped('child_ids').mapped('phone'))) if rec.partner_id.child_ids else ''

    ##############################
#    @api.model
#    def web_search_read(self, domain, specification, offset=0, limit=None, order=None, count_limit=None):
#        _logger.error(f'self.env.company.sudo().must_create_orders_json  {self.env.company.sudo().must_create_orders_json}')
        #if self.env.company.sudo().must_create_orders_json and len(self.env.company.sudo().must_create_orders_json)>0:
            #self._cron_create_update_sale_order()
            #self.env['sale.order'].sudo().import_sale_order(self.env['woocommerce.instance'].
             #   sudo().search([], limit=1, order='id desc'), is_force_update=True, from_method='search_read')
            #self.env.company.sudo().must_create_orders = {}
#        return super().web_search_read(domain, specification, offset=offset, limit=limit, order=order, count_limit=count_limit)

    # @api.model_create_multi
    # def create(self, vals_list):
    #
    #     for vals in vals_list:
    #         _logger.info('\n\n\n\n  create_sale_3order  self =  %s \n\n\n\n' % (7) )
    #         # _logger.info('\n\n\n\n  create_sale_order  self =  %s \n\n\n\n' % (vals['pricelist_id']) )
    #         # if vals['pricelist_id']:
    #         #     pricelist_id = self.env['product.pricelist'].sudo().search([('id', '=', vals['pricelist_id'])], limit=1)
    #         #     woocomm_instance_id = self.env['woocommerce.instance'].sudo().search([('id', '=', vals['woocomm_instance_id'])], limit=1)
    #         #     if pricelist_id.currency_id.name != woocomm_instance_id.wooc_currency:
    #         #         raise UserError(_("The Pricelist currency and WooCommerce currency does not match. \n\nPlease update the pricelist currency or authenticate WooCommerce instance again!!!"))
    #
    #     return super(SaleOrder,self).create(vals_list)
        
    @api.onchange("invoice_count")
    def update_invoice_instance_id(self):
        for id in self.invoice_ids:
            id.woocomm_instance_id = self.woocomm_instance_id
            
    @api.depends('invoice_count')
    def _set_invoice_instance_id(self):
        for order in self:
            invoices = order.order_line.invoice_lines.move_id.filtered(lambda r: r.move_type in ('out_invoice', 'out_refund'))
        for invoice in invoices:
            invoice.woocomm_instance_id = self.woocomm_instance_id


    def init_wc_api(self, wooc_instance=False):
#        wooc_instance = self.env['woocommerce.instance'].sudo().search([('woocomm_instance_id', '=', wooc_instance.id)], limit=1, order='id desc')
        if wooc_instance.is_authenticated:
            try:
                woo_api = API(
                            url=wooc_instance.shop_url,
                            consumer_key=wooc_instance.wooc_consumer_key,
                            consumer_secret=wooc_instance.wooc_consumer_secret,
                            # wp_api=True,
                            version=wooc_instance.wooc_api_version
                        )
                req_data = woo_api.get("")

                return woo_api
            except Exception as error:
                raise UserError(_("Please check your connection and try again"))
        else :
            raise UserError(_("Connection Instance needs to authenticate first. \n Please try after authenticating connection!!!"))
        
    def get_all_orders(self, wooc_instance, limit=10, from_method=None):
        woo_api = self.init_wc_api(wooc_instance)

        _logger.error(f"ctx.get('from_cron') from_method  {from_method}")

        #must_create_orders_json = list(self.env.company.sudo().must_create_orders_json.values()) if self.env.company.sudo().must_create_orders_json else []
        #url = f"orders" + f'?include={",".join(str(order_create) for order_create in must_create_orders_json)}' if must_create_orders_json and from_method != 'cron' else 'orders'
        url = f"orders"
        limit = 4
        get_next_page = True
        page = 1
        while page < 3:
            try:
                params = {'orderby': 'id', 'order': 'desc', 'per_page': limit, 'page': page}
                orders = woo_api.get(url, params=params)
                page += 1

            except Exception as error:
                _logger.info('\n\n\n\n  Error Order on page=  %s \n\n\n\n' % (page) )
                time.sleep(2)
                continue

            if orders.status_code == 200:
                if orders.content:
                    parsed_orders = orders.json()
                    for order in parsed_orders:
                        yield order
                        
                    if len(parsed_orders) < limit:
                        get_next_page = False 
                else:
                    get_next_page = False 
            else:
                    get_next_page = False 
                    
    def cron_import_woocomm_orders(self):
        all_instances = self.env['woocommerce.instance'].sudo().search([])
        # for rec in all_instances:
        #     if rec:
        #         self.env['sale.order'].import_sale_order(rec)

    def import_customer_c(self):
        # woo_api = self.init_wc_api(1)
        ctx = dict(self.env.context)
        # new_record_created = int(ctx.get("new_record_created", 0))
        wcapi = API(url="https://odoo.nstore.ma", port=80, consumer_key="ck_d3ab1d563397dbaf337ac054af32e7ab97db957f", consumer_secret="cs_9709ed568304a0fe2b4d4e328d8e7a67be7d1ec0", wp_api=True, version="wc/v3")
        products = wcapi.get(f'products/29557')
        new_order = products.json()

    def cron_create_update_sale_order(self):
        wooc_instance = self.woocomm_instance_id
        self.import_sale_order(wooc_instance, is_force_update=True, from_method='cron')

    def import_sale_order(self, instance_id, is_force_update = False, from_method=None):
        orders = self.get_all_orders(instance_id, from_method=from_method)

        for order in orders:
            if not is_force_update:
                exist = self.sudo().search([('wooc_id', '=', order['id']), ('woocomm_instance_id', '=', instance_id.id)],limit=1)
                if exist:
                    continue
            
            _logger.info('\n\n  Importing Sale Order Data - #%s \n\n' % (order["id"]))
            if not isinstance(order, str):
                self.create_sale_order(order, instance_id, from_method)
        return

    def create_sale_order(self, order, instance_id, from_method=None):
        # _logger.error('////  order ////')
        # _logger.error(order)
        res_partner = self.env['res.partner'].sudo().search(
                    [('wooc_user_id', '=', order['customer_id']), ('woocomm_instance_id', '=', instance_id.id)], limit=1)
        
        if not res_partner:
            if not order.get('customer_id', 0):
                customer_data = {}
                customer_billing = False
                billing_data = order.get('billing', False)
                shipping_data = order.get('shipping', False)
                if billing_data.get('first_name', False) or billing_data.get('last_name', False):
                    customer_billing = True
                    res_partner = self.env['res.partner'].sudo().create({
                        'name': billing_data.get('first_name', False) + ' ' + billing_data.get('last_name', False),
                        'street': billing_data.get('address_1', False),
                        'city': billing_data.get('city', False),
                        'phone': billing_data.get('phone', False),
                        'mobile': billing_data.get('phone', False),
                        'email': billing_data.get('email', False),
                    })
                if not customer_billing and shipping_data.get('first_name', False) or shipping_data.get('last_name', False):
                    res_partner = self.env['res.partner'].sudo().create({
                        'name': shipping_data.get('first_name', False) + ' ' + shipping_data.get('last_name', False),
                        'street': shipping_data.get('address_1', False),
                        'city': shipping_data.get('city', False),
                        'phone': shipping_data.get('phone', False),
                        'mobile': shipping_data.get('phone', False),
                        'email': shipping_data.get('email', False),
                    })
            else:
                customer_data  = self.env['res.partner'].get_wooc_customer(order['customer_id'], instance_id)
                self.env['res.partner'].create_customer(customer_data, instance_id)

                res_partner = self.env['res.partner'].sudo().search(
                        [('wooc_user_id', '=', order['customer_id']), ('woocomm_instance_id', '=', instance_id.id)], limit=1)
        if res_partner:
            
            dict_so = {}
            dict_so['wooc_id'] = order['id']
            dict_so['partner_id'] = res_partner.id                
            dict_so['name'] = "#" + order['number']
            dict_so['woocomm_instance_id'] = instance_id.id
            dict_so['woocomm_order_no'] = order['number']
            dict_so['woocomm_customer_id'] = order['customer_id']
            dict_so['company_id'] = instance_id.wooc_company_id.id
            dict_so['state'] = 'sale'
            dict_so['woocomm_order_subtotal'] = float(order['total'])
            dict_so['woocomm_order_total_tax'] = float(order['total_tax'])
            dict_so['woocomm_order_total'] = float(order['total'])
            dict_so['woocomm_order_date'] = order['date_created']
            dict_so['amount_total'] = float(order['total'])
            dict_so['woocomm_payment_method'] = order['payment_method']
            dict_so['woocomm_status'] = order['status']
            dict_so['woocomm_order_note'] = order['customer_note']
            dict_so['is_exported'] = True                

            _logger.info('\n\n  create_sale_order  dict_so =  %s \n\n' % (dict_so) )



            sale_order = self.env['sale.order'].sudo().search([('wooc_id', '=', order['id']), ('woocomm_instance_id', '=', instance_id.id)], limit=1)
            if not sale_order:
                
                dict_so['payment_term_id'] = self.create_payment_terms(order) 
                dict_so['is_woocomm_order'] = True
                
                so_obj = self.env['sale.order'].sudo().create(dict_so)

                create_invoice = self.create_woocomm_sale_order_lines(so_obj.id, instance_id, order)
                
                self.create_woocomm_shipping_lines(so_obj.id, instance_id, order)
                                    
                #if order["date_paid"]:
                    # so_obj.action_confirm()

                 #   if create_invoice == True:
                  #      so_obj._create_invoices()
                        
                # To cancel the cancelled orders from woocommerce
                if order['status'] == "cancelled":
                    soc = self.env['sale.order.cancel'].sudo().create({'order_id' : so_obj.id})
                    soc.action_cancel()
                    
                self.env.cr.commit()  
            else:
                if sale_order.state != 'done' or True:
                                  
                    sale_order.sudo().with_context(dont_send_data_to_wooc_from_write_method=True).write(dict_so)
                    lines_ids = [line_ord['id'] for line_ord in order['line_items']]
                    _logger.error('===  lines_ids  ===')
                    _logger.error(lines_ids)
                   # _logger.error([int(woo_so_line_id) for woo_so_line_id in sale_order.order_line.mapped('woocomm_so_line_id') if int(woo_so_line_id) in lines_ids])
                    for sol_item in order['line_items']:
                        res_product = self.env['product.product'].sudo().search(
                            [('woocomm_instance_id', '=', instance_id.id),'|', ('woocomm_variant_id', '=', sol_item.get('product_id')), ('woocomm_variant_id', '=', sol_item.get('variation_id'))],
                            limit=1)

                        if res_product:
                            s_order_line = self.env['sale.order.line'].sudo().search(
                                [('product_id', '=', res_product.id), ('order_id', '=', sale_order.id), ('order_id.woocomm_instance_id', '=', instance_id.id)], limit=1)

                            if s_order_line:
                                tax_id_list= self.add_tax_lines( instance_id, sol_item.get('taxes'))
                        
                                so_line = self.env['sale.order.line'].sudo().search(
                                    [('order_id.woocomm_instance_id', '=', instance_id.id), '&', ('product_id', '=', res_product.id),
                                        (('order_id', '=', sale_order.id))], limit=1)
                                if so_line:
                                    so_line_data = {
                                        'name': res_product.name,                                        
                                        'product_id': res_product.id,
                                        'woocomm_so_line_id': sol_item.get('id'),
                                        'tax_id': [(6, 0, tax_id_list)],
                                        'product_uom_qty': sol_item.get('quantity'),                                        
                                        'price_unit': float(sol_item.get('price')) if sol_item.get('price') != '0.00' else 0.00,                                        
                                    }

                                    sol_update = so_line.with_context(dont_send_data_to_wooc_from_write_method=True).write(so_line_data)
                            else:
                                so_line = self.create_sale_order_line(sale_order.id, instance_id, sol_item)
                                
                        self.env.cr.commit()

                    if order['shipping_lines']:
                        if not self.env.context.get("dont_send_data_to_wooc_from_write_method"):


                            for sh_line in order['shipping_lines']:
                                shipping = self.env['delivery.carrier'].sudo().search(['&', ('woocomm_method_id', '=', sh_line['method_id']), ('woocomm_instance_id', '=', instance_id.id)], limit=1)    
                                
                                so_line = self.env['sale.order.line'].sudo().search(['&', ('is_delivery', '=', True),(('order_id', '=', sale_order.id)), ('order_id.woocomm_instance_id', '=', instance_id.id)], limit=1)
                                if shipping and shipping.product_id:
                                    
                                    tax_id_list = self.add_tax_lines(instance_id, sh_line.get('taxes'))
                                    shipping_vals = {
                                        'product_id': shipping.product_id.id,
                                        'name':shipping.product_id.name,
                                        'price_unit': float(sh_line['total']),
                                        'is_delivery' : True,
                                        'tax_id': [(6, 0, tax_id_list)]
                                    }
                                    if shipping.product_id.id == so_line.product_id.id:
                                        _logger.info('\n\n so_shipping_line_data -- %s  \n\n' % (shipping_vals))
                                        shipping_update = so_line.with_context(dont_send_data_to_wooc_from_write_method=True).write(shipping_vals)
                                    else:
                                        shipping_vals.update({"woocomm_so_line_id":sh_line['id'],'order_id': sale_order.id,})
                                        so_line.with_context(dont_send_data_to_wooc_from_write_method=True).unlink()
                                        self.env['sale.order.line'].sudo().create(shipping_vals)

                                    self.env.cr.commit()

                    else:
                        #To remove shipping price, if the shipping not selected in the woocommerce site due shipping conditions.
                        so_line = self.env['sale.order.line'].sudo().search(['&', ('is_delivery', '=', True),(('order_id', '=', sale_order.id)), ('order_id.woocomm_instance_id', '=', instance_id.id)], limit=1)
                        
                        if so_line:
                            so_line.unlink()

                    # To cancel the cancelled orders from woocommerce
                    if order['status'] == "cancelled":
                        soc = self.env['sale.order.cancel'].sudo().create({'order_id' : sale_order.id})
                        soc.action_cancel()                         

        return


    def create_woocomm_sale_order_lines(self, so_id, instance_id, order):

        create_invoice = False
        for sol_item in order.get('line_items'):
            
            so_line = self.create_sale_order_line(so_id, instance_id, sol_item)
            if so_line:
                if so_line.qty_to_invoice > 0:
                    create_invoice = True
            
        return create_invoice
   
    def create_sale_order_line(self, so_id, instance_id, line_item):
        res_product = ''
        if line_item.get('product_id') or line_item.get('variation_id'):
            res_product = self.env['product.product'].sudo().search(
                [('woocomm_instance_id', '=', instance_id.id),'|', ('woocomm_variant_id', '=', line_item.get('product_id')), ('woocomm_variant_id', '=', line_item.get('variation_id'))],
                limit=1)
            
            if not res_product:
                _logger.info('\n\n\n\n  Product not exist to create Order  =  %s \n\n\n\n' % (line_item) )
                
                self.env['product.template'].sudo().get_wooc_product_data(line_item.get('product_id'), instance_id)
                res_product = self.env['product.product'].sudo().search(
                [('woocomm_instance_id', '=', instance_id.id), '|', ('woocomm_variant_id', '=', line_item.get('product_id')), ('woocomm_variant_id', '=', line_item.get('variation_id'))],
                limit=1)
                
                # need to check about creating product using existing function
                
            if res_product:
                dict_l = {}
                dict_l['woocomm_so_line_id'] = line_item.get('id')
                dict_l['order_id'] = so_id
                dict_l['product_id'] = res_product.id
                dict_l['name'] = res_product.name
                dict_l['product_uom_qty'] = line_item.get('quantity')
                dict_l['price_unit'] = float(line_item.get('price')) if line_item.get('price') != '0.00' else 0.00
                
                if line_item.get('taxes'):
                    _logger.info('\n\n\n\n  Taxes  =  %s \n\n\n\n' % (line_item.get('taxes')) )
                    tax_id_list= self.add_tax_lines(instance_id, line_item.get('taxes'))
                    dict_l['tax_id'] = [(6, 0, tax_id_list)]
                                   
                if line_item.get('currency'):
                    cur_id = self.env['res.currency'].sudo().search([('name', '=', line_item.get('currency'))], limit=1)
                    dict_l['currency_id'] = cur_id.id
                    
                return self.env['sale.order.line'].with_context(dont_send_data_to_wooc_from_write_method=True).sudo().create(dict_l)
            
            return False
  
    def create_payment_terms(self, order):

        if order['payment_method_title']:
            pay_id = self.env['account.payment.term']
            payment = pay_id.sudo().search([('name', '=', order['payment_method_title'])], limit=1)
            if not payment:
                create_payment = payment.sudo().create({'name': order['payment_method_title']})
                if create_payment:
                    return create_payment.id
            else:
                return payment.id
        return False  

    def create_woocomm_shipping_lines(self, so_id, instance_id, order):
        for sh_line in order['shipping_lines']:
            shipping = self.env['delivery.carrier'].sudo().search(['&', ('woocomm_method_id', '=', sh_line['method_id']), ('woocomm_instance_id', '=', instance_id.id)], limit=1)
            if not shipping:
                delivery_product = self.env['product.product'].sudo().create({
                    'name': sh_line['method_title'],
                    'detailed_type': 'service',
                    'taxes_id': [(6, 0, [])]
                })
                               
                vals = {
                    'wooc_id': sh_line['id'],
                    'name': sh_line['method_title'],
                    'product_id': delivery_product.id,
                    'fixed_price': float(sh_line['total']),
                    'woocomm_method_id' : sh_line['method_id'],
                    'is_woocomm': True,
                    'woocomm_instance_id': instance_id.id,                    
                }
                shipping = self.env['delivery.carrier'].sudo().create(vals)
                

            tax_id_list = self.add_tax_lines(instance_id, sh_line.get('taxes'))
            _logger.info('\n\n\n\n  shipping tax %s  \n\n\n\n' % (tax_id_list) )
                       
            if shipping and shipping.product_id:
                shipping_vals = {
                    "woocomm_so_line_id":sh_line['id'],
                    'product_id': shipping.product_id.id,
                    'name':shipping.product_id.name,
                    'price_unit': float(sh_line['total']),
                    'order_id': so_id,
                    'is_delivery' : True,
                    'tax_id': [(6, 0, tax_id_list)]
                }
                shipping_so_line = self.env['sale.order.line'].sudo().create(shipping_vals)
                
        self.env.cr.commit()
        
    def add_tax_lines(self, instance_id, tax_lines):
        
        tax_id_list = []
        if tax_lines:
            for tax_line in tax_lines:
               
                tax_data = self.env['account.tax'].sudo().get_wooc_tax(tax_line['id'], instance_id)
                
                if tax_data:
                    acc_tax = self.env['account.tax'].sudo().create_tax(tax_data, instance_id)
                    tax_id_list.append(acc_tax.id)                  
            
        return tax_id_list   
  
    def woocomm_order_update_button(self):

        woo_api = self.init_wc_api(self.woocomm_instance_id)

        data =  { 
                 "customer_note": self.woocomm_order_note,
                 "status": self.woocomm_status,
                 }
        headers = {
            "X-Odoo-Origin": "true"  # Custom header to indicate the request originated from Odoo
        }
        data_with_headers = {**data, "headers": headers}

        r_data = woo_api.put("orders/%s"%self.wooc_id, data_with_headers)
        r_data = woo_api.get("orders/%s"%self.wooc_id)

        if r_data.status_code == 200:
            _logger.error(f'r_data.json()==>  {r_data.json()}')
            return self.env['message.wizard'].success("Data Updated")
        else:
            return self.env['message.wizard'].fail("Data Update Failed")
                    
    def get_current_order(self):
        selected_ids = self.env.context.get('active_ids', [])
        order_id = self.sudo().search([('id', 'in', selected_ids), ('woocomm_instance_id', '=', self.woocomm_instance_id.id)])

        if not order_id:
            raise UserError(_("Please select Order!!!"))
        else:
            return order_id
 
    def is_cancelled(self):
        if self.state == "cancel":
            raise UserError(_("This action cann't perform in a cancelled order."))       

    def action_woocomm_order_wizard(self):
        
        self.is_cancelled()
        
        action = self.env.ref("mt_odoo_woocommerce_connector.action_woocomm_order_actions_wizard").read()[0]
        action.update({
            'context': "{'woocomm_instance_id': " + str(self.woocomm_instance_id.id) + "}",
        })        
        return action
    
    
    # WooCommerce Refund Code
    def order_refund_create(self, instance_id):
        
        order_ids = self.get_current_order()
        
        for order in order_ids: 
            self.woocomm_full_refund(instance_id, order)
            
    def woocomm_full_refund(self, instance_id, order):
        woo_api = self.init_wc_api(instance_id)
        
        data = {}       
        data.update( {'reason' : "Full refund from odoo", "api_refund" : False})
        
        data['line_items'] = []
        so_lines = self.env['sale.order.line'].sudo().search([('order_id', '=', order.id), ('woocomm_instance_id', '=', instance_id.id)])
        for line in so_lines:
            if line.woocomm_so_line_id and int(line.product_uom_qty) > 0 and not line.is_delivery:
                line_items = {
                    "id": line.woocomm_so_line_id,
                    "quantity": int(line.product_uom_qty),
                    "refund_total": line.price_subtotal,
                    "refund_tax": []
                }
                line_items['refund_tax'].append({"id": "1", "refund_total": line.price_tax })
                data['line_items'].append(line_items)
                
            if line.woocomm_so_line_id and int(line.product_uom_qty) > 0 and line.is_delivery:
                
                tax_items = {"id": line.woocomm_so_line_id, "refund_total": line.price_subtotal, 'refund_tax' : []}
                tax_items['refund_tax'].append({"id": "1", "refund_total": line.price_tax })
                data['line_items'].append(tax_items)  
                                           
            
        try:
            headers = {
                "X-Odoo-Origin": "true"  # Custom header to indicate the request originated from Odoo
            }
            data_with_headers = {**data, "headers": headers}

            wc_refund = woo_api.post("orders/%s/refunds"%order.wooc_id, data_with_headers)
            
            _logger.info('\n\n\n\n Result Refund Array   =  %s \n\n\n\n' % (wc_refund.json()) )  
            
            if wc_refund.status_code == 201:
                if wc_refund.content:
                    refund = wc_refund.json()
            
        except Exception as error:
            _logger.info('\n\n\n\n  Error   =  %s \n\n\n\n' % (error.response.__dict__) )
            raise UserError(_(error.response.body))
  
    def woocomm_order_cancel(self, instance_id):

        woo_api = self.init_wc_api(instance_id)
        
        order_id = self.get_current_order()
        data =  { "status": 'cancelled',}

        headers = {
            "X-Odoo-Origin": "true"  # Custom header to indicate the request originated from Odoo
        }
        data_with_headers = {**data, "headers": headers}

        cancel_order = woo_api.put("orders/%s"%order_id.wooc_id, data_with_headers)
        if cancel_order.status_code == 200:
            cancel_order = cancel_order.json()
            soc = self.env['sale.order.cancel'].sudo().create({'order_id' : order_id.id})
            soc.action_cancel()
            
            order_id.woocomm_status = cancel_order['status']
            
            return self.env['message.wizard'].success("Order Cancelled!!!")
        else:
            return self.env['message.wizard'].fail("Failed to Cancel the order.")   

    def woocomm_force_info_update(self, instance_id):
        woo_api = self.init_wc_api(instance_id)
               
        order_id = self.get_current_order()
        
        try:
            order = woo_api.get("orders/%s"%order_id.wooc_id,)
            
            if order.status_code == 200:
                self.create_sale_order(order.json(), instance_id, from_method='woocomm_force_info_update')
        
        except Exception as error:
            raise UserError(_(error))          
              
# Create new orders
    def woocomm_new_orders(self, instance_id):
               
        order_ids = self.get_current_order()
        
        for order in order_ids: 
            self.create_woocomm_new_order(instance_id, order)
     
    def create_woocomm_new_order(self, instance_id, order):
        woo_api = self.init_wc_api(instance_id)
        
        data = {}       
        data.update({   "customer_id": order.partner_id.wooc_user_id,
                        'line_items' : [],
                        'shipping_lines' : []})
        
        data_cus = self.get_order_address(order.partner_id)
        data.update(data_cus)
        _logger.info('\n\n\n\n  new sale order customer data =  %s \n\n\n\n' % (data_cus) )
        
        so_lines = self.env['sale.order.line'].sudo().search([('order_id', '=', order.id), ('woocomm_instance_id', '=', instance_id.id)])
        for line in so_lines:
            if line.product_id.woocomm_variant_id and int(line.product_uom_qty) > 0:
                line_items = {
                    "product_id": line.product_id.product_tmpl_id.wooc_id,
                    "quantity": int(line.product_uom_qty),
                }
                if line.product_id.woocomm_variant_id :
                    line_items.update({"variation_id": line.product_id.woocomm_variant_id,})
                
                data['line_items'].append(line_items)
                
            if line.is_delivery:
                shipping_line = self.env['delivery.carrier'].sudo().search([('product_id', '=', line.product_id.id), ('woocomm_instance_id', '=', instance_id.id)], limit=1)
                
                data_shipping_line = {}

                data_shipping_line.update({"method_id": shipping_line.woocomm_method_id,
                                           "method_title": shipping_line.name,
                                           })

                    
                if float(line.price_unit) != float(shipping_line.fixed_price):
                    data_shipping_line.update({"total": str(line.price_unit)})
                else:
                    data_shipping_line.update({"total": str(shipping_line.fixed_price)})
                    
                data['shipping_lines'].append(data_shipping_line)
                
        _logger.info('\n\n\n\n  new sale order data =  %s \n\n\n\n' % (data) )
        headers = {
            "X-Odoo-Origin": "true"  # Custom header to indicate the request originated from Odoo
        }
        data_with_headers = {**data, "headers": headers}

        new_order = woo_api.post("orders", data_with_headers)

        if new_order.status_code == 400:            
            if(new_order.json()['code'] == 'woocommerce_rest_invalid_shipping_item'):
                #import all shipping methods from WooCommerce
                self.env['delivery.carrier'].import_shipping_method(instance_id)
                
                raise UserError(_("Shippping Method Not Exist!!!, \nChoose correct method from list, thats under the current store instance!!!"))

        
        if new_order.status_code == 201:
            new_order = new_order.json()   
            #
            # _logger.error(f'new_order  ==>=> {new_order}')
            # _logger.error(new_order)

            order.update({'wooc_id' : new_order['id'], 'is_exported':True, 'name' : "#" + new_order['number'] })
            
            # To create Order data in db after exporting.
            self.create_sale_order(new_order, instance_id, from_method='woocomm_new_orders')
            
            order.update({'is_woocomm_order' : False })
                      
    def get_order_address(self, customer):
        
            contacts_billing = self.env['res.partner'].sudo().search([('parent_id', '=', customer.id), ('woocomm_instance_id', '=', self.woocomm_instance_id.id), ('type', '=', 'invoice')],limit=1)
            contacts_delivery = self.env['res.partner'].sudo().search([('parent_id', '=', customer.id), ('woocomm_instance_id', '=', self.woocomm_instance_id.id), ('type', '=', 'delivery')],limit=1)
            
            if customer:
                email = getattr(customer, 'email') or ''
            
            if contacts_billing:
                billing_addr = self.env['res.partner'].sudo().set_address(contacts_billing)
            else:     
                billing_addr = self.env['res.partner'].sudo().set_address(customer)  
                        
            if contacts_delivery:
                delivery_addr = self.env['res.partner'].sudo().set_address(contacts_delivery)
            else:     
                delivery_addr = billing_addr          
            
            billing_addr.update({'email' : email})            
            
            return {"billing" : billing_addr , "shipping" : delivery_addr }

# set paid manually in woocommerce
    def woocomm_set_paid(self, instance_id):
        woo_api = self.init_wc_api(instance_id)

        order_ids = self.get_current_order()

        for order in order_ids: 
            data =  { 
                    "set_paid": True,
                    }
            headers = {
                "X-Odoo-Origin": "true"  # Custom header to indicate the request originated from Odoo
            }
            data_with_headers = {**data, "headers": headers}

            r_data = woo_api.put("orders/%s"%order.wooc_id, data_with_headers)
            
        if r_data.status_code == 200:
            
            self.create_sale_order(r_data.json(), instance_id, from_method='woocomm_set_paid')
            
            return self.env['message.wizard'].success("Data Updated")
        else:
            return self.env['message.wizard'].fail("Data Update Failed")            

    def action_generate_invoice(self):
        
        self.is_cancelled()
        
        action = self.env.ref("mt_odoo_woocommerce_connector.action_woocomm_wizard_generate_invoice").read()[0]
        action.update({
            'context': "{'woocomm_instance_id': " + str(self.woocomm_instance_id.id) + "}",
        })         
        return action

    def order_generate_invoice(self, instance_id):
               
        order_ids = self.get_current_order()
        
        for order in order_ids:
            for order_invoice in  order.invoice_ids:
                if order_invoice.state == "draft":
                    order_invoice.action_post() #to confirm invoice 

                if order_invoice.state == "posted" and order_invoice.payment_state == "not_paid":
                    order_invoice.action_register_payment() #to register payment 

    def woocomm_order_update_buttons(self, rec):
        # wooc_instance = self.env['woocommerce.instance'].sudo().search([], limit=1, order='id desc')
        wooc_instance = rec.woocomm_instance_id
        if wooc_instance:
            woo_api = self.init_wc_api(wooc_instance)
            data = {
                "customer_note": rec.woocomm_order_note,
                "status": rec.woocomm_status,
            }
            headers = {
                "X-Odoo-Origin": "true"
            }
            data_with_headers = {**data, "headers": headers}
    
            r_data = woo_api.put("orders/%s" % rec.wooc_id, data_with_headers)
            if r_data.status_code == 200:
                return self.env['message.wizard'].success("Data Updated")
            else:
                return self.env['message.wizard'].fail("Data Update Failed")

           
    def write(self, values):
        rtn = super().write(values)
        if (values.get('woocomm_status', False) or values.get('woocomm_order_note', False)) and not self.env.context.get("dont_send_data_to_wooc_from_write_method"):
            for rec in self:
                self.woocomm_order_update_buttons(rec)
        return rtn


import inspect


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    woocomm_so_line_id = fields.Char('WooCommerce Line ID')
    
    woocomm_vendor = fields.Many2one('res.partner', 'WooCommerce Vendor')
    order_wooc_id = fields.Char(related='order_id.wooc_id')

    def write(self, values):
        rtn = super().write(values)
        
        # Skip if we shouldn't send data to WooCommerce
        # if self.env.context.get("dont_send_data_to_wooc_from_write_method"):
        #     return rtn
        
        # Check if we're adding a new line (no woocomm_so_line_id yet)
        is_new_line = not self.woocomm_so_line_id and self.order_wooc_id
        # if not self.env.context.get("dont_send_data_to_wooc_from_write_method"):

        # Handle both updates and new line additions
        if (self.woocomm_so_line_id or is_new_line) and self.order_wooc_id:
            woo_api = self.order_id.init_wc_api(self.order_id.woocomm_instance_id)
            url = f"orders/{self.order_wooc_id}"
            
            # Get current order data from WooCommerce
            wooc_order = woo_api.get(url).json()
            
            # Prepare the data structure - we'll send only the fields WooCommerce expects
            data = {"line_items": []}
            
            if is_new_line:
                # This is a NEW line being added to the order
                new_item = {
                    "product_id": int(self.product_template_id.wooc_id),
                    "quantity": float(values.get('product_uom_qty', self.product_uom_qty))
                }
                
                # Handle variable products
                if self.product_template_id.woocomm_product_type == 'variable':
                    new_item["variation_id"] = int(self.product_id.woocomm_variant_id)
                
                # Set pricing if provided
                if values.get('price_unit', False):
                    new_item.update({
                        'total': str(values.get('price_total', self.price_total)),
                        'subtotal': str(values.get('price_subtotal', self.price_total))
                    })
                
                data["line_items"].append(new_item)
            else:
                # This is an EXISTING line being updated
                line_items_data = wooc_order.get('line_items', [])
                for line_item in line_items_data:
                    if line_item.get('id') == int(self.woocomm_so_line_id):
                        # Create a clean item with only the fields we want to update
                        item_update = {
                            "id": int(line_item["id"]),
                            "quantity": float(values.get('product_uom_qty', self.product_uom_qty))
                        }
                        
                        if values.get('price_unit', False):
                            item_update.update({
                                'total': str(values.get('price_total', self.price_total)),
                                'subtotal': str(values.get('price_subtotal', self.price_total))
                            })
                        
                        data["line_items"].append(item_update)
            
            # For new lines, merge with existing items but clean them first
            if is_new_line:
                existing_items = []
                for item in wooc_order.get('line_items', []):
                    # Create a clean version of each existing item
                    clean_item = {
                        "id": int(item["id"]),
                        "product_id": int(item["product_id"]),
                        "quantity": float(item["quantity"]),
                        "price": float(item.get("price", 0)),
                    }
                    
                    # Add variation_id if it exists
                    if item.get("variation_id"):
                        clean_item["variation_id"] = int(item["variation_id"])
                    
                    existing_items.append(clean_item)
                
                data["line_items"] = existing_items + data["line_items"]
            
            # _logger.error(f'data ===> {data}')
            if not self.env.context.get("dont_send_data_to_wooc_from_write_method"):
            
                try:
                    _logger.error(f'TRY == TRY == TRY == TRY == TRY == TRY')

                    # Send the update to WooCommerce
                    response = woo_api.put(url, data)
                    
                    if response.status_code != 200:
                        error_msg = f"Failed to update WooCommerce order. Status: {response.status_code}, Response: {response.text}"
                        _logger.error(error_msg)
                        raise UserError(_('Could not update WooCommerce order: %s') % response.text)
                    
                    # Update Odoo with WooCommerce order totals if successful
                    order_data = response.json()
                    self.order_id.update({
                        'woocomm_order_subtotal': float(order_data.get('total', 0)),
                        'woocomm_order_total_tax': float(order_data.get('total_tax', 0)),
                        'woocomm_order_total': float(order_data.get('total', 0)),
                    })
                    
                    # For new lines, store the WooCommerce line item ID
                    if is_new_line and not self.woocomm_so_line_id:
                        # Find the new line item in the response
                        new_line_item = next(
                            (item for item in order_data.get('line_items', []) 
                            if item.get('product_id') == int(self.product_template_id.wooc_id) and
                                (self.product_template_id.woocomm_product_type != 'variable' or 
                                item.get('variation_id') == int(self.product_id.woocomm_variant_id))),
                            None
                        )
                        
                        if new_line_item:
                            self.with_context(dont_send_data_to_wooc_from_write_method=True).write({'woocomm_so_line_id': str(new_line_item['id'])})
                            
                except Exception as e:
                    _logger.error("Error updating WooCommerce order: %s", str(e))
                    raise UserError(_('Error communicating with WooCommerce: %s') % str(e))
        
        return rtn

    def unlink(self):
        import json
        _logger.error(f"Deleting line items: {self}")
        for rec in self:
            if rec.woocomm_so_line_id and rec.order_wooc_id:
                # Initialize WooCommerce API
                woo_api = rec.order_id.init_wc_api(self.order_id.woocomm_instance_id)
                url = f"orders/{rec.order_wooc_id}"

                # Fetch the WooCommerce order
                wooc_order = woo_api.get(url).json()
                line_items_data = wooc_order.get('line_items', [])

                # Prepare the data to update the order
                data = {"line_items": []}
                for line_item in line_items_data:
                    if line_item['id'] == int(rec.woocomm_so_line_id):
                        # Set quantity to 0 for the line item to be deleted
                        data["line_items"].append({
                            'quantity': 0,
                            "id": line_item["id"],
                        })
                        # Set quantity to 0 for the line item to be deleted
                        updated_line_item = {
                            'quantity': 0,
                            "id": line_item["id"],
                        }
                        # Ensure meta_data is properly formatted
                        if 'meta_data' in line_item:
                            updated_line_item['meta_data'] = []
                            for meta in line_item['meta_data']:
                                if 'display_value' in meta and isinstance(meta['display_value'], dict):
                                    # Convert display_value to a JSON string
                                    meta['display_value'] = json.dumps(meta['display_value'])
                                updated_line_item['meta_data'].append(meta)
                        data["line_items"].append(updated_line_item)


                        # Handle parent_name field
                        if 'parent_name' in line_item and line_item['parent_name'] is None:
                            updated_line_item['parent_name'] = ""  # Replace None with an empty string
                        elif 'parent_name' in line_item:
                            updated_line_item['parent_name'] = line_item['parent_name']  # Keep existing value


                        # Set quantity to 0 for the line item to be deleted
#                        data["line_items"].append({
#                            'quantity': 0,
#                            "id": line_item["id"],
#                        })
                    else:
                        # Keep other line items unchanged
                        if 'parent_name' in line_item:
                            line_item['parent_name'] = str(line_item['parent_name']) if line_item['parent_name'] is not None else ""
                        else:
                            line_item['parent_name'] = ""  # Default to empty string if not present
                        data["line_items"].append(line_item)

                # Log the data being sent to WooCommerce
                _logger.error(f'Data being sent to WooCommerce: {data}')

                # Prepare headers
                headers = {
                    "X-Odoo-Origin": "true"  # Custom header to indicate the request originated from Odoo
                }

                # Send the PUT request to update the order
                put_wooc_order = woo_api.put(f'orders/{rec.order_wooc_id}', data=data)

                # Log the response from WooCommerce
                _logger.error(f'WooCommerce API Response: {put_wooc_order.status_code}, {put_wooc_order.json()}')

                # Handle the response
                if put_wooc_order.status_code != 200:
                    raise UserError('Cannot delete line item from WooCommerce. Please check the logs for details.')
                else:
                    # Update the Odoo order with the latest data from WooCommerce
                    order = put_wooc_order.json()
                    rec.order_id.update({
                        'woocomm_order_subtotal': float(order['total']),
                        'woocomm_order_total_tax': float(order['total_tax']),
                        'woocomm_order_total': float(order['total']),
                    })

        return super().unlink()

    def _check_line_unlink(self):
        """ Check whether given lines can be deleted or not.

        * Lines cannot be deleted if the order is confirmed.
        * Down payment lines who have not yet been invoiced bypass that exception.
        * Sections and Notes can always be deleted.

        :returns: Sales Order Lines that cannot be deleted
        :rtype: `sale.order.line` recordset
        """
        return self.filtered(
            lambda line:
                line.state == 'sale' and not line.woocomm_so_line_id
                and (line.invoice_lines or not line.is_downpayment)
                and not line.display_type
        )

