# -*- coding: utf-8 -*-
import time
import logging

from woocommerce import API
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class Customer(models.Model):
    _inherit = 'res.partner'
    
    @api.model
    def default_get(self, fields):
        res = super(Customer, self).default_get(fields)
        if self.env['woocommerce.instance']._context.get('woocomm_instance_id'):
            res['woocomm_instance_id'] = self.env['woocommerce.instance']._context.get('woocomm_instance_id')
        return res

    wooc_user_id = fields.Char('WooCommerce User ID')

    is_exported = fields.Boolean('Synced In WooCommerce', default=False)
    is_woocomm_customer = fields.Boolean('Is WooCommerce Customer', default=False)

    woocomm_instance_id = fields.Many2one('woocommerce.instance', ondelete='cascade')
    
    def init_wc_api(self, wooc_instance):
        # wooc_instance = self.env['woocommerce.instance'].search([], limit=1, order='id desc')
#        wooc_instance = self.woocomm_instance_id
        if wooc_instance.is_authenticated:
            try:
                woo_api = API(
                            url=wooc_instance.shop_url,
                            consumer_key=wooc_instance.wooc_consumer_key,
                            consumer_secret=wooc_instance.wooc_consumer_secret,
                            wp_api=True,
                            version=wooc_instance.wooc_api_version
                        )
                req_data = woo_api.get("")
                
                return woo_api
            except Exception as error:
                raise UserError(_("Please check your connection and try again"))
        else :
            raise UserError(_("Connection Instance needs to authenticate first. \n Please try after authenticating connection!!!"))
        
    def get_all_customers(self, wooc_instance, limit=100):
        woo_api = self.init_wc_api(wooc_instance)
                
        url = "customers"
        get_next_page = True
        page = 1
        while get_next_page:
            try:
                customers = woo_api.get(url, params={'orderby': 'id', 'order': 'asc','per_page': limit, 'page': page})
                page += 1

            except Exception as error:
                _logger.info('\n\n\n\n  Error Customers on page=  %s \n\n\n\n' % (page) )
                time.sleep(2)
                continue
            
            if customers.status_code == 200:
                if customers.content:
                    parsed_customers = customers.json()
                    for customer in parsed_customers:
                        yield customer
                        
                    if len(parsed_customers) < limit:
                        get_next_page = False 
                else:
                    get_next_page = False 
            else:
                    get_next_page = False

    def export_customers(self, wooc_instance):
        woo_api = self.init_wc_api(wooc_instance)
        
        selected_ids = self.env.context.get('active_ids', [])
        selected_records = self.env['res.partner'].sudo().browse(selected_ids)
        all_records = self.env['res.partner'].sudo().search([('woocomm_instance_id', '=', wooc_instance.id)])
        if selected_records:
            records = selected_records
        else:
            records = all_records

        export_list = []

        for rec in records:
            
            if rec.wooc_user_id:
                is_exist = self.get_wooc_customer(rec.wooc_user_id, wooc_instance)
                if not is_exist:
                    rec.wooc_user_id = False
            
            billing_addr = {}
            dict_contacts = {}

            contacts_billing = self.env['res.partner'].sudo().search([('parent_id', '=', rec.id), ('type', '=', 'invoice'), ('woocomm_instance_id', '=', wooc_instance.id)],limit=1)
            contacts_delivery = self.env['res.partner'].sudo().search([('parent_id', '=', rec.id), ('type', '=', 'delivery'), ('woocomm_instance_id', '=', wooc_instance.id)],limit=1)
            
            if rec:
                dict_contacts['email'] = getattr(rec, 'email') or '' #str(rec.email) or ''
                if rec.name:
                    dict_contacts['first_name']= rec.name.split()[0]
                    dict_contacts['last_name']= rec.name.split()[1] if len(rec.name.split()) == 2 else ""
            
            if contacts_billing:
                billing_addr = self.set_address(contacts_billing)
            else:     
                billing_addr = self.set_address(rec)  
                
            if contacts_delivery:
                delivery_addr = self.set_address(contacts_delivery)
            else:     
                delivery_addr = billing_addr                
                 

            export_list.append({"id" : rec.wooc_user_id, "details" :   {
                            "first_name": dict_contacts['first_name'],
                            "last_name": dict_contacts['last_name'],
                            "email": dict_contacts['email'],
                            "verified_email": True,
                            "billing": billing_addr,
                            "shipping": delivery_addr
                    }})
        if export_list:
            for data in export_list:
                if data.get("id"):
                    try:
                        result = woo_api.put("customers/%s" %data.get("id"), data.get("details")).json()
                        _logger.info('\n\n\n\n  update result export_customers=  %s \n\n\n\n' % (result) )
                    
                    except Exception as error:
                        _logger.info('\n\n\n\n Error ------ %s \n\n\n\n\n' % error)
                        raise UserError(_("Please check your connection and try again"))

                else:
                    try:
                        result = woo_api.post("customers", data.get("details")).json()
                        _logger.info('\n\n\n\n  result export_customers=  %s \n\n\n\n' % (result) )
                    except Exception as error:
                        _logger.info('\n\n\n\n Error new customer ------ %s \n\n\n\n\n' % error)
                        raise UserError(_("Please check your connection and try again"))
                    
        self.import_customer(wooc_instance)

    def cron_import_woocomm_customers(self):
        all_instances = self.env['woocommerce.instance'].sudo().search([])
        for rec in all_instances:
            if rec:
                self.env['res.partner'].import_customer(rec)

    def import_customer(self, instance_id):
        for customer in self.get_all_customers(instance_id):
            self.create_customer(customer, instance_id)
            
        return

    def create_customer(self, customer, wooc_instance):
        existing_customer = self.env['res.partner'].sudo().search([('wooc_user_id', '=', customer.get('id')), ('woocomm_instance_id', '=', wooc_instance.id)], limit=1)
        ''' 
            This is used to update wooc_user_id of a customer, this
            will avoid duplication of customer while syncing customers.
        '''
        customer_without_wooc_user_id = self.env['res.partner'].sudo().search(
            [('wooc_user_id', '=', False), ('woocomm_instance_id', '=', wooc_instance.id), ('email', '=', customer.get('email')), ('type', '=', 'contact')], limit=1)

        contact_details = {}
        first = customer.get('first_name')
        last = customer.get('last_name')        
            
        contact_details['wooc_user_id'] = customer.get('id')
        contact_details['email'] = customer.get('email')
        contact_details['phone'] = customer.get('phone')
        contact_details['name'] = contact_details['email'] if (not first.strip() and not last.strip()) else first.strip() + " " + last.strip()

        dict_p = {}
        
        dict_p['woocomm_instance_id'] = wooc_instance.id
        dict_p['company_id'] = wooc_instance.wooc_company_id.id
        dict_p['is_exported'] = True
        dict_p['is_woocomm_customer'] = True
        dict_p['customer_rank'] = 1
        dict_p.update(contact_details)
        
        # _logger.info('\n\n\n\n import records data %s \n\n\n\n\n' % dict_p)

        if not existing_customer and customer_without_wooc_user_id:
            customer_without_wooc_user_id.sudo().write(dict_p)
            
        
        if not existing_customer and not customer_without_wooc_user_id:
            ''' If customer is not present we create it '''
            new_customer = self.env['res.partner'].sudo().create(dict_p)
            if new_customer:              
                # to add address id to contact type entry in res.partner 

                if customer.get('billing'):
                    #billing
                    self.create_address(customer.get('billing'), new_customer.id, 'invoice', 'Invoice create import ')
                
                if customer.get('shipping'):
                    #shipping
                    self.create_address(customer.get('shipping'), new_customer.id, 'delivery', 'Delivery create import ')
                
                self.env.cr.commit()
        else:
            update_customer = existing_customer.sudo().write(dict_p)
            if update_customer:
                ''' Search for updated customer '''
                customer_record = self.env['res.partner'].sudo().search([('wooc_user_id', '=', customer.get('id')), ('woocomm_instance_id', '=', wooc_instance.id)],limit=1)
                if customer_record:
                    '''Invoice Address Update/Create'''
                    self.update_or_create_address(wooc_instance, customer_record.id, customer.get('billing'), 'invoice')
                    
                    '''Delivery Address Update/Create'''
                    self.update_or_create_address(wooc_instance, customer_record.id, customer.get('shipping'), 'delivery')
                    
                self.env.cr.commit()
            
        return  
     
    def get_wooc_customer(self, customer_id, instance_id):
        woo_api = self.init_wc_api(instance_id)
        wc_customer = woo_api.get("customers/%s"%customer_id,)
        if wc_customer.status_code == 200:
            if wc_customer.content:
                customer_data = wc_customer.json()
                return customer_data
        
        return False     
     
    def update_or_create_address(self, wooc_instance, record_id, address, addr_type='invoice'):
        '''Search for customer id'''
        customer_id = self.env['res.partner'].sudo().search(
            [('parent_id', '=', record_id), ('type', '=', addr_type), ('woocomm_instance_id', '=', wooc_instance.id)],limit=1)
        if customer_id:
            #update
            self.update_existing_address(address, customer_id, addr_type, 'address Updated')
        else:
            #create
            self.create_address(address, record_id, addr_type, 'create address import EXISTING CUSTOMER')

    def create_address(self, address_data, parent_id, addr_type='invoice', log_str=''):
        
        address= self.address_array(address_data)
        dict_a = {}
        dict_a.update(address)
        dict_a['is_company'] = False
        dict_a['parent_id'] = parent_id
        dict_a['type'] = addr_type   

        if dict_a['name']:
            if log_str !='':
                _logger.info('\n\n\n\n %s  %s \n\n\n\n\n' % (log_str, dict_a))
            address_create = self.env['res.partner'].sudo().create(dict_a)
    
    def update_existing_address(self, address_data, customer_data, addr_type='invoice', log_str=''):
        
        address= self.address_array(address_data)
        
        if log_str !='':
                _logger.info('\n\n\n\n %s  %s \n\n\n\n\n' % (log_str, address))
        if address.get('country'):
            if address['state_id'] and address['state_id'] != '':
                customer_data.sudo().write({'state_id': address['state_id']})
            addr_arr = {
                'name': address.get('name'),
                'zip': address.get('zip'),
                'city': address.get('city'),
                'street': address.get('street'),
                'street2': address.get('street2'),
                'country_id': address.get('country_id'),
                'phone': address.get('phone'),
                'parent_id': customer_data.parent_id,
                'type': addr_type
            }
            address_update_data = customer_data.sudo().write(addr_arr)
    
    def address_array(self, address_data ):
        address= {}
        address['name'] = address_data.get('first_name') + " " + address_data.get('last_name')
        # address['company'] = address_data.get('company')
        address['street'] = address_data.get('address_1')
        address['street2'] = address_data.get('address_2')
        address['city'] = address_data.get('city')
        address['zip'] = address_data.get('postcode')
        address['email'] = address_data.get('email')
        address['phone'] = address_data.get('phone')
        
        address_country = address_data.get('country')
        address_state = address_data.get('state')

        if address_country:
            country_id = self.env['res.country'].sudo().search(
                [('code', '=', address_country)],limit=1)
            address['country_id'] = country_id.id
            if address_state:
                state_id = self.env['res.country.state'].sudo().search(
                    ['&', ('code', '=',address_state),
                        ('country_id', '=', country_id.id)],limit=1)

                address['state_id'] = state_id.id if state_id else ''
                
        return address
    
    def set_address(self, addr_rec):
        addr = {}
        if addr_rec.name:
            addr['first_name']= addr_rec.name.split()[0]
            addr['last_name']= addr_rec.name.split()[1] if len(addr_rec.name.split()) == 2 else ''
        addr['address_1'] = getattr(addr_rec, 'street') or ''
        addr['address_2'] = getattr(addr_rec, 'street2') or ''
        addr['city'] = getattr(addr_rec, 'city') or ''
        addr['state'] = getattr(addr_rec, 'state_id').code if getattr(addr_rec, 'state_id').code else ''
        addr['postcode'] = getattr(addr_rec, 'zip') or ''
        addr['country'] = getattr(addr_rec, 'country_id').code if getattr(addr_rec, 'country_id').code else ''
        addr['phone'] = getattr(addr_rec, 'phone') or ''
        return addr
'''
address Updated  {'name': ' ', 'street': '', 'street2': '', 'city': '', 'zip': '', 'email': None, 'phone': ''}
'''
