# -*- coding: utf-8 -*-
import logging

from woocommerce import API
from odoo.exceptions import UserError, MissingError
from odoo import models, api, fields, SUPERUSER_ID, _
from odoo.tools import config
from bs4 import BeautifulSoup
config['limit_time_real'] = 10000000
config['limit_time_cpu'] = 600
from odoo.exceptions import ValidationError
from odoo.osv import expression


_logger = logging.getLogger(__name__)
from odoo.tools.float_utils import float_round


class MFStockQuant(models.Model):
    _inherit = 'stock.quant'

    mf_show_product = fields.Boolean(string="Show Product", compute='_mf_show_product', store=True)

    @api.depends('product_id', 'product_id.wooc_id', 'product_id.product_tmpl_id.wooc_id')
    def _mf_show_product(self):
        for rec in self:
            rec.show_product = True


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    sales_counts = fields.Float(
        string="Sold", digits='Product Unit of Measure',store=True)

    variant_count_product_type = fields.Char(compute='depends_on_product_variant_count')

    @api.depends('woocomm_product_type', 'product_variant_count')
    def depends_on_product_variant_count(self):
        for rec in self:
            rec.woocomm_product_type = 'variable' if rec.product_variant_count > 1 else 'simple'
            rec.variant_count_product_type = ''

    # Be aware that the exact same function exists in product.product
    def action_open_quants(self):
        model_stock_location, model_stock_quant, action_open_quants = self.env['stock.location'], self.env['stock.quant'], self.product_variant_ids.filtered(lambda p: p.active)

        if not model_stock_quant.sudo().search([('product_id', 'in', action_open_quants.ids), ('product_id.woocomm_instance_id', '=', self.woocomm_instance_id.id)]):
            for location in model_stock_location.search([('usage', 'in', ['internal', 'transit'])]):
                [model_stock_quant.create({'product_id': product.id, 'location_id': location.id}) for product in action_open_quants
                 if not model_stock_quant.sudo().search([('product_id', '=', product.id), ('product_id.woocomm_instance_id', '=', self.woocomm_instance_id.id)])]
#                 if not model_stock_quant.sudo().search([('product_id', '=', product.id), ('location_id', '=', location.id)])]
            action_open_quants = self.product_variant_ids.filtered(lambda p: p.active)


            if not self.woocomm_variant_ids and self.product_variant_count > 1 and self.wooc_id:
                action_open_quants = self.product_variant_ids.filtered(lambda p: p.woocomm_variant_id)

            return action_open_quants.action_open_quants()


        if not self.woocomm_variant_ids and self.product_variant_count > 1 and self.wooc_id:
            action_open_quants = self.product_variant_ids.filtered(lambda p: p.woocomm_variant_id)
            return action_open_quants.action_open_quants()

        return super().action_open_quants()

    def write(self, values):
        rtn = super().write(values)
        product_ids = self.env['product.product'].search([('product_tmpl_id', '=', self.id), ('woocomm_instance_id', '=', self.woocomm_instance_id.id)]).ids
        woo_variants = self.env['woocommerce.product.variant'].search(
                [('product_template_id', '=', self.id), ('product_variant_id', 'in', product_ids), ('product_template_id.woocomm_instance_id', '=', self.woocomm_instance_id.id)])
        [r.update({
            'wooc_sale_price': values.get('woocomm_sale_price', r.wooc_sale_price),
            'wooc_regular_price': values.get('woocomm_regular_price', r.wooc_regular_price),
        }) for r in woo_variants if values.get('woocomm_sale_price', False) or values.get('woocomm_regular_price', False)]
        return rtn

    @api.model
    def web_search_read(self, domain, specification, offset=0, limit=None, order=None, count_limit=None):
        if self.env.context.get('getProductSortedBySalesCount', False):
            order = 'sales_counts desc'
            rtn = super().web_search_read(domain, specification, offset=offset, limit=limit, order=order, count_limit=count_limit)
        return super().web_search_read(domain, specification, offset=offset, limit=limit, order=order, count_limit=count_limit)

    def unlink(self):
        for product_templ in self:
            if product_templ.is_exported and product_templ.wooc_id:
                woo_api = self.init_wc_api(self.woocomm_instance_id)
                remove_product = woo_api.delete(f"products/{product_templ.wooc_id}")
                _logger.error(remove_product)
                if remove_product.status_code == 200:
                    _logger.error('Product was deleted from woocommerce with success')
                else:
                    raise ValidationError(remove_product.json())
        return super().unlink()


class StockQuant(models.Model):
    _inherit = 'stock.quant'


    show_product = fields.Boolean(string="Show Product")
    product_wooc_id = fields.Char(string="Product WooCommerce ID", related='product_id.wooc_id', store=True)
    product_woocomm_variant_id = fields.Char(string="Product VAR WooCommerce ID", related='product_id.woocomm_variant_id', store=True)

    @api.model
    def _unlink_zero_quants(self):
        """ _update_available_quantity may leave quants with no
        quantity and no reserved_quantity. It used to directly unlink
        these zero quants but this proved to hurt the performance as
        this method is often called in batch and each unlink invalidate
        the cache. We defer the calls to unlink in this method.
        """
        precision_digits = max(6, self.sudo().env.ref('product.decimal_product_uom').digits * 2)
        # Use a select instead of ORM search for UoM robustness.
        query = """SELECT id FROM stock_quant WHERE (round(quantity::numeric, %s) = 0 OR quantity IS NULL)
                                                     AND round(reserved_quantity::numeric, %s) = 0
                                                     AND (round(inventory_quantity::numeric, %s) = 0 OR inventory_quantity IS NULL)
                                                     AND user_id IS NULL;"""
        params = (precision_digits, precision_digits, precision_digits)
        self.env.cr.execute(query, params)
        quant_ids = self.env['stock.quant'].browse([quant['id'] for quant in self.env.cr.dictfetchall()])
        # quant_ids.sudo().unlink()

    def init_wc_api(self, wooc_instance):
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
        else:
            raise UserError(
                _("Connection Instance needs to authenticate first. \n Please try after authenticating connection!!!"))

    def write(self, values):
        super().write(values)
        if self.location_id.id == 8 and not self.env.context.get("dont_send_data_to_wooc_from_write_method") and self.product_id.wooc_id and (values.get('inventory_quantity_auto_apply', False) or values.get('inventory_quantity_auto_apply', '') == 0) or (self.product_id.wooc_id and (values.get('quantity', '') == 0 or values.get('quantity', False)) and self.location_id.id == 8):
            _logger.error(f'\n\n Quantity changed values {values}')

            woocomm_instance_id = self.product_id.woocomm_instance_id if self.product_id.woocomm_instance_id else self.product_id.product_tmpl_id.woocomm_instance_id
            woo_api = self.init_wc_api(woocomm_instance_id)
            p_type = self.product_id.product_tmpl_id.woocomm_product_type

            var_quant_data = {
                "stock_quantity": self.inventory_quantity_auto_apply,
                "manage_stock": True
            }

            if p_type == "variable":
                _logger.error(f'var_quant_data = {var_quant_data}')
                stock_quantity_update = woo_api.put("products/%s/variations/%s" % (
                str(self.product_id.wooc_id), str(self.product_id.woocomm_variant_id)), var_quant_data)

                result = stock_quantity_update.json()

                wooc_variant = self.env['woocommerce.product.variant'].sudo().search(
                    [('wooc_id', '=', self.product_id.woocomm_variant_id), ('product_template_id.woocomm_instance_id', '=', self.product_id.woocomm_instance_id.id)])

                data = {"wooc_stock_quantity": result["stock_quantity"], "is_manage_stock": result["manage_stock"]}
                if wooc_variant:
                    wooc_variant.write(data)
#                    self.env.cr.commit()

            elif p_type == "simple":
                stock_quantity_update = woo_api.put("products/%s" % (str(self.product_id.wooc_id)), var_quant_data)


class WooCommerceProductVariants(models.Model):
    _name = 'woocommerce.product.variant'
    _description = 'WooCommerce Product Variants'
    _order = "wooc_id desc"

    wooc_id = fields.Char(string="WooCommerce Variant id")
    name = fields.Char(string="WooCommerce Variant Name")
    wooc_variant_image = fields.Binary(string="WooCommerce Image", attachment=True)
    wooc_sku = fields.Char(string="WooCommerce SKU")
    wooc_regular_price = fields.Char(string="WooCommerce Regular Price")
    wooc_sale_price = fields.Char(string="WooCommerce Sale Price")
    wooc_stock_quantity = fields.Char(string="WooCommerce Stock Quantity")
    wooc_stock_status = fields.Selection([('instock', "In Stock"),('outofstock', "Out of Stock"),('onbackorder', "On Backorder")], string="Stock Status", default="instock") 
    wooc_v_weight = fields.Char(string="Weight")
    wooc_v_dimension_length = fields.Char(string="Length")
    wooc_v_dimension_width = fields.Char(string="Width")
    wooc_v_dimension_height = fields.Char(string="Height")
    wooc_variant_description = fields.Char(string="WooCommerce Description")
    
    is_enabled = fields.Boolean(default = True, help="Variant Enabled Or Not")
    is_manage_stock  = fields.Boolean(default = False, string="Manage Stock")  

    product_template_id = fields.Many2one('product.template', string='Product template', ondelete='cascade')
    product_variant_id = fields.Many2one('product.product', string='Product Variant', ondelete='cascade')
    file_name = fields.Char("File Name", readonly=True)
    woocomm_instance_id = fields.Many2one('woocommerce.instance', string='WooCommerce Instance')

    def write(self, vals):
        
        if vals.__contains__('wooc_stock_quantity'):
            if vals['wooc_stock_quantity'] == 'None':
                vals['wooc_stock_quantity'] = 0
        
        rtn = super(WooCommerceProductVariants, self).write(vals)

        if (vals.__contains__('wooc_v_weight') or vals.__contains__('wooc_v_dimension_length') or vals.__contains__('wooc_variant_image')
                or vals.__contains__('wooc_v_dimension_width') or vals.__contains__('wooc_v_dimension_height')
                or vals.__contains__('wooc_sale_price') or vals.__contains__('wooc_regular_price')
                or vals.__contains__('wooc_sku') or vals.__contains__('is_enabled') or vals.__contains__('wooc_stock_status')):
            # variant_image =
            self.env.cr.commit()
            # if not self.env.context.get("dont_send_data_to_wooc_from_write_method"):

            self.wooc_variations_update(self)
       
    def init_wc_api(self, wooc_instance):
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
        
    def wooc_variations_update(self, variant):
        variation_id = variant.wooc_id
        product_tmpl = self.product_template_id
        product_wooc_id = product_tmpl.wooc_id
        product_product_id = variant.product_variant_id
        with_image, src = False, ''
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        if variant.file_name:
            with_image, src = True, f'{base_url}/web/image/woocommerce.product.variant/{variant.id}/wooc_variant_image/{variant.file_name}'
        woo_api = self.init_wc_api(product_tmpl.woocomm_instance_id)

        data = {
                "sale_price": str(variant.wooc_sale_price),
                "regular_price": str(variant.wooc_regular_price),
                # "sku" : variant.wooc_sku,
                "stock_status" : variant.wooc_stock_status,
                "status" : "publish" if variant.is_enabled else "private",
                "purchasable" : True if variant.is_enabled else False,
                "weight": str(variant.wooc_v_weight),
                "dimensions": {
                    "length": str(variant.wooc_v_dimension_length),
                    "width": str(variant.wooc_v_dimension_width),
                    "height": str(variant.wooc_v_dimension_height)
                },
            }
        if variant.wooc_sku:
            data['sku'] = variant.wooc_sku
        if with_image:
            data['image'] = {'src': src}
        if not self.env.context.get("dont_send_data_to_wooc_from_write_method"):
            wc_variation = woo_api.post("products/%s/variations/%s"%(product_wooc_id,variation_id), data).json()
        else:
            wc_variation = woo_api.get("products/%s/variations/%s"%(product_wooc_id,variation_id)).json()


        product_variant_id = product_variant = self.env['product.product'].sudo().search([('product_tmpl_id', '=', product_tmpl.id), ('woocomm_variant_id', '=', variation_id), ('woocomm_instance_id', '=', self.woocomm_instance_id.id)])
        product_product_id.write({
                'woocomm_regular_price' : float(wc_variation["regular_price"]) if wc_variation["regular_price"] else 0,
                'lst_price' : float(wc_variation["sale_price"]) if wc_variation["sale_price"] else 0,
                # 'list_price' : float(wc_variation["regular_price"]) if wc_variation["regular_price"] else 0,
                'woocomm_sale_price' : float(wc_variation["sale_price"]) if wc_variation["sale_price"] else 0
            })
        variant.product_variant_id.write({
                'woocomm_regular_price' : float(wc_variation["regular_price"]) if wc_variation["regular_price"] else 0,
                'woocomm_sale_price' : float(wc_variation["sale_price"]) if wc_variation["sale_price"] else 0,
                'lst_price' : float(wc_variation["sale_price"]) if wc_variation["sale_price"] else 0,
                # 'list_price' : float(wc_variation["regular_price"]) if wc_variation["regular_price"] else 0,

            })

        self.write({'wooc_stock_quantity' : str(wc_variation["stock_quantity"]),
                     'is_manage_stock' : wc_variation["manage_stock"],
                    #  'wooc_regular_price': float(wc_variation["regular_price"]) if wc_variation["regular_price"] else 0,
                    # 'wooc_sale_price': float(wc_variation["sale_price"]) if wc_variation["sale_price"] else 0,
                     
                     })
        _logger.error(f'wc_variation stock_quantity. {wc_variation.get("stock_quantity", False)}')

        stock_quantity = int(wc_variation.get('stock_quantity', '0'))

        if stock_quantity:

            InventoryWizard = self.env['stock.change.product.qty'].with_user(SUPERUSER_ID).sudo()
            inventory_wizard = InventoryWizard.create({
                'product_id': variant.product_variant_id.id,
                'product_tmpl_id': product_tmpl.id,
                'new_quantity': stock_quantity,
            })
        # User has no right on quant, must raise an AccessError
            inventory_wizard.change_product_qty()

        self.env.cr.commit()
