# -*- coding: utf-8 -*-

import json
from woocommerce import API
from odoo import fields, models, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class WooCommerceInstance(models.Model):
    _description = "Woocommerce Instance"
    _name = 'woocommerce.instance'

    name = fields.Char('Instance Name', required=True, help="Name to identify shop")
    shop_url = fields.Char(string="Shop URL", required=True, help="woocommerce access url")
    wooc_consumer_key = fields.Char(string="Consumer Key", required=True, help="generated REST API Consumer Key")
    wooc_consumer_secret = fields.Char(string="Consumer Secret", required=True, help="generated REST API Consumer Secret")
    wooc_api_version = fields.Char(string="API Version", required=True,  help="API Version", default="wc/v3")
    wooc_dashboard_graph_data = fields.Text(compute='_kanban_wooc_dashboard_graph')
    wooc_currency = fields.Char(string="WooCommerce Currency")
    
    active = fields.Boolean('Active', default=True)
    is_authenticated = fields.Boolean('Authenticated or Not', default=False)
    
    wooc_company_id = fields.Many2one('res.company', string="Company")


    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            _logger.info('\n\n\n\n  vals  =  %s \n\n\n\n' % (vals) )
            instance_count = self.sudo().search_count([('id', '!=', 0)])
            if instance_count >= 1:
                raise UserError(_("Only One Instance can Create!!!"))
            
            return super(WooCommerceInstance,self).create(vals)
            
    def write(self, vals):

        if vals.__contains__('shop_url') or vals.__contains__('wooc_consumer_key') or vals.__contains__('wooc_consumer_secret') or vals.__contains__('wooc_api_version'):
            vals['is_authenticated'] = False

        super(WooCommerceInstance, self).write(vals)
        self.env.cr.commit()        

    #authenticate current instance
    def connection_authenticate(self):
        
        if not self.id:
            return
        
        try:
            wcapi = API(
                        url=self.shop_url,
                        consumer_key=self.wooc_consumer_key,
                        consumer_secret=self.wooc_consumer_secret,
                        wp_api=True,
                        version=self.wooc_api_version
                    )
            req_data = wcapi.get("")
                 
        except:
            return self.env['message.wizard'].fail("Connection Unsuccessful..!! \nPlease check your Shop Url, Consumer Key or Consumer Secret / Try Again")

        if req_data.status_code == 200:
            self.is_authenticated = False
            currency = wcapi.get("data/currencies/current").json()           
            if currency["code"] == self.wooc_company_id.currency_id.name :
                _logger.info('\n\n\n\n  Currency  =  %s \n\n\n\n' % (currency["code"]) )
                self.wooc_currency = currency["code"]
                self.is_authenticated = True
                
                return self.env['message.wizard'].success("Congratulations, \nWooCommerce and Odoo connection has been successfully verified.")
            else:
                return self.env['message.wizard'].fail("Congratulations, \nWooCommerce and Odoo connection has been successfully verified. \n But Currency Not Matching")
            
        else:
            raise UserError(
                _("Connection Unsuccessful..!! \nPlease check your Shop Url, Consumer Key or Consumer Secret / Try Again"))

    def _kanban_wooc_dashboard_graph(self):

        if not self._context.get('sort'):
            context = dict(self.env.context)
            context.update({'sort': 'month'}) #default chart view for order data
            self.env.context = context

        for rec in self:
            values = rec.get_dashboard_data_woocommerce(rec)
            sales_total = round(sum([key['y'] for key in values]), 2)
            woocomm_orders_data = rec.get_total_orders()
            woocomm_products_data = rec.get_products()
            woocomm_customers_data = rec.get_customers()
            woocomm_attribute_data = rec.get_woocomm_attribute()
            woocomm_category_data = rec.get_woocomm_category()
            woocomm_taxes_data = rec.get_taxes()
            rec.wooc_dashboard_graph_data = json.dumps({
                "title": "",                
                "key": "Untaxed Amount",
                "values": values,                
                "sort_on": self._context.get('sort'),                
                "sales_total": sales_total,
                "shop_orders": woocomm_orders_data,
                "shop_products": woocomm_products_data,
                "shop_customers": woocomm_customers_data,
                "woocomm_attributes": woocomm_attribute_data,
                "woocomm_category": woocomm_category_data,
                "shop_taxes": woocomm_taxes_data,
                "shop_currency_symbol": rec.wooc_company_id.currency_id.symbol or '',
            })

    #get order data to show in graph.
    def get_dashboard_data_woocommerce(self, record):

        def graph_data_year(record):
            self._cr.execute("""select TRIM(TO_CHAR(DATE_TRUNC('month',month),'MONTH')),sum(amount_untaxed) from
                                    (
                                    SELECT 
                                      DATE_TRUNC('month',date(day)) as month,
                                      0 as amount_untaxed
                                    FROM generate_series(date(date_trunc('year', (current_date)))
                                        , date(date_trunc('year', (current_date)) + interval '1 YEAR - 1 day')
                                        , interval  '1 MONTH') day
                                    union all
                                    SELECT DATE_TRUNC('month',date(date_order)) as month,
                                    sum(amount_untaxed) as amount_untaxed
                                      FROM   sale_order
                                    WHERE  date(date_order) >= (select date_trunc('year', date(current_date))) AND date(date_order)::date <= (select date_trunc('year', date(current_date)) + '1 YEAR - 1 day')
                                    and woocomm_instance_id = %s and state in ('sale','done')
                                    group by DATE_TRUNC('month',date(date_order))
                                    order by month
                                    )foo 
                                    GROUP  BY foo.month
                                    order by foo.month""" % record.id)
            return self._cr.dictfetchall()

        def graph_data_month(record):
            self._cr.execute("""select EXTRACT(DAY from date(date_day)) :: integer,sum(amount_untaxed) from (
                        SELECT 
                          day::date as date_day,
                          0 as amount_untaxed
                        FROM generate_series(date(date_trunc('month', (current_date)))
                            , date(date_trunc('month', (current_date)) + interval '1 MONTH - 1 day')
                            , interval  '1 day') day
                        union all
                        SELECT date(date_order)::date AS date_day,
                        sum(amount_untaxed) as amount_untaxed
                          FROM   sale_order
                        WHERE  date(date_order) >= (select date_trunc('month', date(current_date)))
                        AND date(date_order)::date <= (select date_trunc('month', date(current_date)) + '1 MONTH - 1 day')
                        and woocomm_instance_id = %s and state in ('sale','done')
                        group by 1
                        )foo 
                        GROUP  BY 1
                        ORDER  BY 1""" % record.id)
            return self._cr.dictfetchall()

        def graph_data_week(record):
            self._cr.execute("""SELECT to_char(date(d.day),'DAY'), t.amount_untaxed as sum
                                FROM  (
                                   SELECT day
                                   FROM generate_series(date(date_trunc('week', (current_date)))
                                    , date(date_trunc('week', (current_date)) + interval '6 days')
                                    , interval  '1 day') day
                                   ) d
                                LEFT   JOIN 
                                (SELECT date(date_order)::date AS day, sum(amount_untaxed) as amount_untaxed
                                   FROM   sale_order
                                   WHERE  date(date_order) >= (select date_trunc('week', date(current_date)))
                                   AND    date(date_order) <= (select date_trunc('week', date(current_date)) + interval '6 days')
                                   AND woocomm_instance_id=%s and state in ('sale','done')
                                   GROUP  BY 1
                                   ) t USING (day)
                                ORDER  BY day;""" % record.id)
            return self._cr.dictfetchall()

        def graph_data_all(record):
            self._cr.execute("""select TRIM(TO_CHAR(DATE_TRUNC('month',date_order),'YYYY-MM')),sum(amount_untaxed)
                                from sale_order where woocomm_instance_id = %s and state in ('sale','done')
                                group by DATE_TRUNC('month',date_order) order by DATE_TRUNC('month',date_order)""" %
                             record.id)
            return self._cr.dictfetchall()

        if self._context.get('sort') == 'week':
            result = graph_data_week(record)
        elif self._context.get('sort') == "month":
            result = graph_data_month(record)
        elif self._context.get('sort') == "year":
            result = graph_data_year(record)
        else:
            result = graph_data_all(record)

        values = [{"x": ("{}".format(data.get(list(data.keys())[0]))), "y": data.get('sum') or 0.0} for data in result]

        return values

    def create_action(self, view, domain, context =""):
        action = {
            'name': view.get('name'),
            'type': view.get('type'),
            'domain': domain,
            'view_mode': view.get('view_mode'),
            'view_id': view.get('view_id')[0] if view.get('view_id') else False,
            'views': view.get('views'),
            'res_model': view.get('res_model'),
            'target': view.get('target'),
            'context' : context
        }

        if 'tree' in action['views'][0]:
            action['views'][0] = (action['view_id'], 'list')

        return action

    #get total orders under current WooCommerce instance.
    def get_total_orders(self):
        instance = self.search([], limit=1, order='id desc')
        query = """select id from sale_order where woocomm_instance_id= %s and state in ('sale','done', 'cancel')""" % instance.id

        def week_orders(query):
            w_query = query + " and date(date_order) >= (select date_trunc('week', date(current_date))) order by date(date_order)"
            self._cr.execute(w_query)

            return self._cr.dictfetchall()

        def month_orders(query):
            m_query = query + " and date(date_order) >= (select date_trunc('month', date(current_date))) order by date(date_order)"
            self._cr.execute(m_query)

            return self._cr.dictfetchall()

        def year_orders(query):
            y_query = query + " and date(date_order) >= (select date_trunc('year', date(current_date))) order by date(date_order)"
            self._cr.execute(y_query)
            return self._cr.dictfetchall()

        def all_orders(record):
            self._cr.execute(
                """select id from sale_order where woocomm_instance_id = %s and state in ('sale','done')""" % instance.id)

            return self._cr.dictfetchall()
        
        shop_orders = {}
        if self._context.get('sort') == "week":
            result = week_orders(query)
        elif self._context.get('sort') == "month":
            result = month_orders(query)
        elif self._context.get('sort') == "year":
            result = year_orders(query)
        else:
            result = all_orders(self)

        order_ids = [data.get('id') for data in result]
        view = self.env.ref('mt_odoo_woocommerce_connector.action_sale_order_tree_woocomm').read()[0]
        context = "{'woocomm_instance_id': " + str(self.id) + "}"
        action = self.create_action(view, [('id', 'in', order_ids)], context)

        shop_orders.update({'order_count': len(order_ids), 'order_action': action})
        return shop_orders

    #get products under current WooCommerce instance.
    def get_products(self):
        shop_products = {}
        total_count = 0

        self._cr.execute(
            """select count(id) as total_count from product_template where woocomm_instance_id = %s""" % self.id)
        result = self._cr.dictfetchall()

        if result:
            total_count = result[0].get('total_count')

        view = self.env.ref('sale.product_template_action').read()[0]
        context = "{'woocomm_instance_id': " + str(self.id) + ", 'search_default_woocomm_imported_products': 1}"
        action = self.create_action(view, [('woocomm_instance_id', '=', self.id)], context)

        shop_products.update({
            'product_count': total_count,
            'product_action': action
        })

        return shop_products

    #get customers under current WooCommerce instance.
    def get_customers(self):
        shop_customers = {}
        self._cr.execute("""select id from res_partner where is_exported = True and woocomm_instance_id = %s""" % self.id)
        result = self._cr.dictfetchall()
        customer_ids = [data.get('partner_id') for data in result]
        view = self.env.ref('account.res_partner_action_customer').read()[0]
        context = "{'woocomm_instance_id': " + str(self.id) + "}"
        action = self.create_action(view, [('is_exported', '=', True), ('woocomm_instance_id', '=', self.id)], context)

        shop_customers.update({
            'customer_count': len(customer_ids),
            'customer_action': action
        })

        return shop_customers
 
    def get_woocomm_attribute(self):
        attribute_data = {}
        self._cr.execute(
            """select id from product_attribute where is_woocomm = True and woocomm_instance_id = %s""" % self.id)
        result = self._cr.dictfetchall()
        attribute_ids = [data.get('attribute_id') for data in result]
        view = self.env.ref('product.attribute_action').read()[0]
        context = "{'woocomm_instance_id': " + str(self.id) + "}"
        action = self.create_action(view, [('is_woocomm', '=', True), ('woocomm_instance_id', '=', self.id)], context)

        attribute_data.update({
            'attr_count': len(attribute_ids),
            'attr_action': action
        })

        return attribute_data
     
    def get_woocomm_category(self):
        category_data = {}
        self._cr.execute(
            """select id from product_category where is_exported = True and woocomm_instance_id = %s""" % self.id)
        result = self._cr.dictfetchall()
        category_ids = [data.get('category_id') for data in result]
        view = self.env.ref('product.product_category_action_form').read()[0]
        context = "{'woocomm_instance_id': " + str(self.id) + "}"
        action = self.create_action(view, [('is_exported', '=', True), ('woocomm_instance_id', '=', self.id)], context)

        category_data.update({
            'category_count': len(category_ids),
            'category_action': action
        })

        return category_data
    
    def get_taxes(self):
        tax_data = {}
        self._cr.execute("""select id from account_tax where is_woocomm_tax = True and woocomm_instance_id = %s""" % self.id)
        result = self._cr.dictfetchall()
        tax_ids = [data.get('tax_id') for data in result]
        view = self.env.ref('account.action_tax_form').read()[0]
        context = "{'woocomm_instance_id': " + str(self.id) + "}"
        action = self.create_action(view, [('is_woocomm_tax', '=', True), ('woocomm_instance_id', '=', self.id)], context)
        tax_data.update({
            'tax_count': len(tax_ids),
            'tax_action': action
        })

        return tax_data
    