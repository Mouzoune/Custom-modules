from odoo import api, fields, models, _
from odoo.tools import float_round
from odoo.exceptions import ValidationError
from odoo.tools.misc import formatLang
from odoo.tools import float_compare, float_is_zero, html_escape

from datetime import datetime
import logging

_logger = logging.getLogger(__name__)



class ProductProduct(models.Model):
    _inherit = 'product.product'

    woocomm_regular_price = fields.Char(default=700)
    woocomm_sale_price = fields.Char(default=600)

class ProductCatalogMixin(models.AbstractModel):
    """ This mixin should be inherited when the model should be able to work
    with the product catalog.
    It assumes the model using this mixin has a O2M field where the products are added/removed and
    this field's co-related model should has a method named `_get_product_catalog_lines_data`.
    """
    _inherit = 'product.catalog.mixin'

    def _get_product_catalog_order_line_info(self, product_ids, **kwargs):
        """ Returns products information to be shown in the catalog.
        :param list product_ids: The products currently displayed in the product catalog, as a list
                                 of `product.product` ids.
        :param dict kwargs: additional values given for inherited models.
        :rtype: dict
        :return: A dict with the following structure:
            {
                'productId': int
                'quantity': float (optional)
                'productType': string
                'price': float
                'readOnly': bool (optional)
            }
        """
        order_line_info = {}
        default_data = self._default_order_line_values()

        for product, record_lines in self._get_product_catalog_record_lines(product_ids).items():
            order_line_info[product.id] = {
               **record_lines._get_product_catalog_lines_data(**kwargs),
               'productType': product.type,
            }
            product_ids.remove(product.id)

        products = self.env['product.product'].browse(product_ids)
        product_data = self._get_product_catalog_order_data(products, **kwargs)
        for product_id, data in product_data.items():
            order_line_info[product_id] = {**default_data, **data}
        return order_line_info

class SaleOrder(models.Model):
    _inherit = 'sale.order'



    def _get_product_catalog_order_data(self, products, **kwargs):
        pricelist = self.pricelist_id._get_products_price(
            quantity=1.0,
            products=products,
            currency=self.currency_id,
            date=self.date_order,
            **kwargs,
        )
        res = super()._get_product_catalog_order_data(products, **kwargs)
        for product in products:
            if product.woocomm_regular_price or product.woocomm_sale_price or product.list_price:
                res[product.id]['price'] = product.lst_price
            else:
                res[product.id]['price'] = pricelist.get(product.id)

            if product.sale_line_warn != 'no-message' and product.sale_line_warn_msg:
                res[product.id]['warning'] = product.sale_line_warn_msg
            if product.sale_line_warn == "block":
                res[product.id]['readOnly'] = True
        return res


    def _update_order_line_info(self, product_id, quantity, **kwargs):
        """ Update sale order line information for a given product or create a
        new one if none exists yet.
        :param int product_id: The product, as a `product.product` id.
        :return: The unit price of the product, based on the pricelist of the
                 sale order and the quantity selected.
        :rtype: float
        """
        sol = self.order_line.filtered(lambda line: line.product_id.id == product_id)
        if sol:
            if quantity != 0:
                sol.product_uom_qty = quantity
            elif self.state in ['draft', 'sent']:
                price_unit = self.pricelist_id._get_product_price(
                    product=sol.product_id,
                    quantity=1.0,
                    currency=self.currency_id,
                    date=self.date_order,
                    **kwargs,
                )
                sol.unlink()
                return price_unit
            else:
                sol.product_uom_qty = 0
        elif quantity > 0:
            sol = self.env['sale.order.line'].create({
                'order_id': self.id,
                'product_id': product_id,
                'product_uom_qty': quantity,
                'sequence': ((self.order_line and self.order_line[-1].sequence + 1) or 10),  # put it at the end of the order
            })
        self.button_compute_custom_prices()
        return sol.price_unit

    @api.model
    def create(self, vals):
        res = super(SaleOrder, self).create(vals)
        if vals.get('order_line', False):
            for order in self:
                if not order.woocomm_instance_id:
                    order.button_compute_custom_prices()
        return res

    def write(self, vals):
        res = super(SaleOrder, self).write(vals)
        if vals.get('order_line', False):
            for order in self:
                if not order.woocomm_instance_id:
                    order.button_compute_custom_prices()
        return res

    def button_compute_custom_prices(self):
        for order in self:
            # Cache original prices if needed
            lines = order.order_line
            lines_by_category = {}

            # Build mapping of category_id -> lines
            for line in lines:
                category = line.product_id.categ_id
                if category:
                    lines_by_category.setdefault(category.id, []).append(line)
                    
            order_date = order.date_order.date() if order.date_order else fields.Date.today()
            
            # Filter rules with multiple categories
            applicable_rules = order.pricelist_id.item_ids.filtered(
                lambda r: r.categ_ids and (
                        (not r.date_start or r.date_start.date() <= order_date) and
                        (not r.date_end or r.date_end.date() >= order_date)
                )
            )

            # Sort rules by min_quantity in descending order to prioritize higher quantities
            applicable_rules = applicable_rules.sorted(key=lambda r: r.min_quantity, reverse=True)
            
            # for rule in rules:
            for rule in applicable_rules:
                # Find lines matching any category in the rule
                matching_lines = []
                total_qty = 0.0

                for categ in rule.categ_ids:
                    for line in lines_by_category.get(categ.id, []):
                        if line not in matching_lines:
                            matching_lines.append(line)
                            total_qty += line.product_uom_qty

                # Apply the rule to the matching lines
                if total_qty <= rule.min_quantity:
                    for line in matching_lines:
                        base_price = line.product_id.lst_price  # default to list price
                        if rule.base == 'list_price':
                            base_price = line.product_id.lst_price
                        elif rule.base == 'standard_price':
                            base_price = line.product_id.standard_price

                        if rule.compute_price == 'fixed':
                            line.price_unit = line.product_id.lst_price - rule.fixed_price if line.product_id.lst_price else 0

                        elif rule.compute_price == 'percentage':
                            line.price_unit = base_price * (1 - (rule.percent_price / 100.0))

                        elif rule.compute_price == 'formula':
                            price = base_price

                            # Apply discount
                            if rule.price_discount:
                                price = price * (1 - rule.price_discount)

                            # Apply rounding
                            if rule.price_round:
                                price = round(price / rule.price_round) * rule.price_round

                            # Apply surcharge
                            price += rule.price_surcharge

                            # Enforce min/max margins
                            if rule.price_min_margin:
                                price = max(price, base_price + rule.price_min_margin)
                            if rule.price_max_margin:
                                price = min(price, base_price + rule.price_max_margin)

                            line.price_unit = price
                        if total_qty < rule.min_quantity:
                            line.price_unit = line.product_id.lst_price


class ProductPriceListItem(models.Model):
    _inherit = 'product.pricelist.item'

    # Change categ_id from many2one to many2many
    categ_ids = fields.Many2many(
        'product.category',
        'pricelist_item_category_rels',
        'item_id', 'categ_id',
        string='Catégories de produits',
        help="Apply this rule to products in selected categories"
    )

    # Keep original categ_id for compatibility during migration
    categ_id = fields.Many2one(
        'product.category',
        string='Product Category (Legacy)',
        help="Legacy single category field - use Categories field instead"
    )
    compute_price = fields.Selection(
        selection=[
            ('fixed', "Fixed Price"),
            ('percentage', "Discount"),
            ('formula', "Formula"),
        ],
        index=True, default='percentage', required=True)

    compute_pricing = fields.Selection(
        selection=[
            ('percentage', "Discount"),
            ('fixed', "Fixed Price"),
        ],
        index=True, default='percentage', required=True, string="Calculer le prix")

    applied_on = fields.Selection(
        selection=[
            ('3_global', "All Products"),
            ('2_product_category', "Product Category"),
            ('1_product', "Product"),
            ('0_product_variant', "Product Variant"),
        ],
        string="Appliquer sur",
        default='2_product_category',
        required=True,
        help="Pricelist Item applicable on selected option")

    applied_on_categ = fields.Selection(
        selection=[
            ('2_product_category', "Catégories de produits"),
        ],
        string="Appliquer sur",
        default='2_product_category',
        required=True,
        help="Pricelist Item applicable on selected option")

    #=== ONCHANGE METHODS ===#
    @api.onchange('compute_pricing')
    def onchange_compute_pricing(self):
        self.compute_price = self.compute_pricing

    @api.onchange('applied_on_categ')
    def onchange_applied_on_categ(self):
        self.applied_on = self.applied_on_categ

    @api.onchange('categ_ids')
    def onchange_categ_ids(self):
        self.categ_id = self.categ_ids[0].id if self.categ_ids else False

    @api.depends('applied_on', 'categ_id', 'product_tmpl_id', 'product_id', 'compute_price', 'fixed_price', \
        'pricelist_id', 'percent_price', 'price_discount', 'price_surcharge')
    def _compute_name_and_price(self):
        for item in self:
            if item.categ_id and item.applied_on == '2_product_category':
                item.name = _("Category: %s", item.categ_id.display_name)
            if item.categ_ids and item.applied_on == '2_product_category':
                item.name = _("Category: %s", ', '.join(item.categ_ids.mapped('display_name')))
            elif item.product_tmpl_id and item.applied_on == '1_product':
                item.name = _("Product: %s", item.product_tmpl_id.display_name)
            elif item.product_id and item.applied_on == '0_product_variant':
                item.name = _("Variant: %s", item.product_id.display_name)
            else:
                item.name = _("All Products")

            if item.compute_price == 'fixed':
                item.price = formatLang(
                    item.env, item.fixed_price, monetary=True, dp="Product Price", currency_obj=item.currency_id)
            elif item.compute_price == 'percentage':
                item.price = _("%s %% discount", item.percent_price)
            else:
                item.price = _("%(percentage)s %% discount and %(price)s surcharge", percentage=item.price_discount, price=item.price_surcharge)

    @api.model
    def create(self, vals):
        """Handle data migration from old categ_id to new categ_ids"""
        res = super().create(vals)
        if vals.get('applied_on_categ', False):
            vals['applied_on'] = vals.get('applied_on_categ')
        return res

    def write(self, vals):
        """Handle data migration from old categ_id to new categ_ids"""
        res = super().write(vals)
        if vals.get('applied_on_categ', False):
            vals['applied_on'] = vals.get('applied_on_categ')
        return res

    def _is_applicable_for(self, product, qty, date=None, **kwargs):
        """Override to handle multiple categories with date parameter"""
        if date is None:
            date = fields.Date.context_today(self)

        if self.applied_on == '2_product_category':
            if not self.categ_ids:
                return False
            # Check if product belongs to any of the selected categories
            if product._name == 'product.product':
                return product.categ_id in self.categ_ids or product.categ_id.id == self.categ_id.id
            return product.categ_id in self.categ_ids or product.categ_id.id == self.categ_id.id
        return super()._is_applicable_for(product, qty, date=date, **kwargs)


class ProductPriceList(models.Model):
    _inherit = 'product.pricelist'

    is_show_product_pricelist = fields.Boolean(
        string='Show in product view',
        default=False,
        groups='product.group_sale_pricelist',
        help='Enable to display this pricelist as a field in product and variant views'
    )

    display_position = fields.Selection(
        [('after_price', 'After Sales Price'),
         ('after_cost', 'After Cost Price'),
         ('custom', 'Custom Position')],
        string='Display Position',
        default='after_price',
        help='Determine where the pricelist field should appear in product views'
    )

    custom_position_field = fields.Char(
        string='Anchor Field',
        help='Specify the field name after which this pricelist should appear (for custom position)'
    )

    def _get_products_for_pricelist_item(self, item):
        """Helper method to get products based on pricelist item scope"""
        if item.applied_on == '3_global':
            return self.env['product.template'].search([])
        elif item.applied_on == '2_product_category':
            if not item.categ_ids:
                return self.env['product.template']
            return self.env['product.template'].search([('categ_id', 'in', item.categ_ids.ids)])
        elif item.applied_on == '0_product_variant':
            return item.product_id
        return item.product_tmpl_id

    def _get_model_info(self, is_variant=False):
        """Return model-specific information based on variant flag"""
        if is_variant:
            return {
                'model': 'product.product',
                'inherit_id': self.env.ref('product.product_product_tree_view'),
                'model_id': self.env.ref('product.model_product_product').id,
                'prefix': 'variant_'
            }
        return {
            'model': 'product.template',
            'inherit_id': self.env.ref('product.product_template_tree_view'),
            'model_id': self.env.ref('product.model_product_template').id,
            'prefix': 'temp_'
        }

    def _create_or_update_field(self, model_info, pricelist_name):
        """Create or update the dynamic field for the pricelist"""
        field_name = f"x_{model_info['prefix']}{self.id}_{pricelist_name}"
        field_description = f"{self.name} Price"

        field = self.env['ir.model.fields'].search([
            ('model_id', '=', model_info['model_id']),
            ('name', '=', field_name)
        ], limit=1)

        if not field:
            field = self.env['ir.model.fields'].sudo().create({
                'name': field_name,
                'field_description': field_description,
                'model_id': model_info['model_id'],
                'ttype': 'float',
                'store': True,
                'help': f"Automatically generated field for {self.name} pricelist"
            })
        return field

    def _generate_view_arch(self, field_name, model_info):
        """Generate the XML architecture for the dynamic view"""
        position_field = {
            'after_price': 'list_price',
            'after_cost': 'standard_price',
            'custom': self.custom_position_field or 'list_price'
        }.get(self.display_position, 'list_price')

        return f'''<?xml version="1.0"?>
            <data>
                <field name="{position_field}" position="after"
                    groups="product.group_sale_pricelist">
                    <field name="{field_name}" optional="show"/>
                </field>
            </data>'''

    def _create_or_update_view(self, model_info, pricelist_name, field_name):
        """Create or update the dynamic view for the pricelist"""
        view_name = f'product.dynamic.fields.{pricelist_name}.{model_info["model"]}'

        view = self.env['ir.ui.view'].search([
            ('name', '=', view_name),
            ('model', '=', model_info['model'])
        ], limit=1)

        arch_base = self._generate_view_arch(field_name, model_info)

        if not view:
            self.env['ir.ui.view'].sudo().create({
                'name': view_name,
                'type': 'tree',
                'model': model_info['model'],
                'mode': 'extension',
                'inherit_id': model_info['inherit_id'].id,
                'arch_base': arch_base,
                'active': True
            })
        else:
            view.write({'arch_base': arch_base})

    def _update_product_prices(self, item, products, field):
        """Update product prices based on pricelist item"""
        if item.compute_price == 'fixed':
            products.write({field.name: item.fixed_price})
        elif item.compute_price == 'percentage':
            base_price = item.base == 'list_price' and 'list_price' or 'standard_price'
            for product in products:
                price = product[base_price] * (1 - item.percent_price / 100)
                product.write({field.name: price})

    def _cleanup_pricelist_artifacts(self, pricelist_name, model_info):
        """Clean up views and fields when pricelist is deleted"""
        views = self.env['ir.ui.view'].search([
            ('name', '=', f'product.dynamic.fields.{pricelist_name}.{model_info["model"]}'),
            ('model', '=', model_info['model'])
        ])
        views.unlink()

        field_name = f"x_{model_info['prefix']}{self.id}_{pricelist_name}"
        self.env['ir.model.fields'].search([
            ('model_id', '=', model_info['model_id']),
            ('name', '=', field_name)
        ]).unlink()

    def check_pricelist_condition(self):
        """Main method to update pricelist display and pricing"""
        if not self.item_ids:
            return

        pricelist_name = self.name.replace(" ", "_")

        for item in self.item_ids:
            is_variant = item.applied_on == '0_product_variant'
            products = self._get_products_for_pricelist_item(item)
            model_info = self._get_model_info(is_variant)

            field = self._create_or_update_field(model_info, pricelist_name)
            self._create_or_update_view(model_info, pricelist_name, field.name)
            self._update_product_prices(item, products, field)

    @api.model
    def create(self, vals):
        """Override create to handle pricelist display setup"""
        pricelist = super().create(vals)
        if pricelist.is_show_product_pricelist:
            pricelist.check_pricelist_condition()
        return pricelist

    def write(self, vals):
        """Override write to handle pricelist display updates"""
        res = super().write(vals)
        if 'is_show_product_pricelist' in vals or 'display_position' in vals or 'custom_position_field' in vals:
            self.check_pricelist_condition()
        return res

    def unlink(self):
        """Clean up dynamic fields and views before deletion"""
        for pricelist in self:
            pricelist_name = pricelist.name.replace(" ", "_")

            # Clean up variant artifacts
            variant_info = self._get_model_info(is_variant=True)
            self._cleanup_pricelist_artifacts(pricelist_name, variant_info)

            # Clean up template artifacts
            template_info = self._get_model_info(is_variant=False)
            self._cleanup_pricelist_artifacts(pricelist_name, template_info)

        return super().unlink()

    @api.constrains('custom_position_field')
    def _check_custom_position_field(self):
        """Validate the custom position field exists"""
        for pricelist in self:
            if pricelist.display_position == 'custom' and not pricelist.custom_position_field:
                raise ValidationError(_("Please specify an anchor field for custom position display."))





# from odoo import api, fields, models, _
# from odoo.tools import float_round
# from odoo.exceptions import ValidationError
# from odoo.tools.misc import formatLang
# from odoo.tools import float_compare, float_is_zero, html_escape

# from datetime import datetime
# import logging

# _logger = logging.getLogger(__name__)


# class SaleOrder(models.Model):
#     _inherit = 'sale.order'

#     @api.model
#     def create(self, vals):
#         res = super(SaleOrder, self).create(vals)
#         if vals.get('order_line', False):
#             for order in self:
#                 if not order.woocomm_instance_id:
#                     order.button_compute_custom_prices()
#         return res

#     def write(self, vals):
#         res = super(SaleOrder, self).write(vals)
#         if vals.get('order_line', False):
#             for order in self:
#                 if not order.woocomm_instance_id:
#                     order.button_compute_custom_prices()
#         return res

#     def button_compute_custom_prices(self):
#         for order in self:
#             # Cache original prices if needed
#             lines = order.order_line
#             lines_by_category = {}

#             # Build mapping of category_id -> lines
#             for line in lines:
#                 category = line.product_id.categ_id
#                 if category:
#                     lines_by_category.setdefault(category.id, []).append(line)
#             order_date = order.date_order.date() if order.date_order else fields.Date.today()

#             # Filter rules with multiple categories
#             applicable_rules = order.pricelist_id.item_ids.filtered(
#                 lambda r: r.categ_ids and (
#                         (not r.date_start or r.date_start.date() <= order_date) and
#                         (not r.date_end or r.date_end.date() >= order_date)
#                 )
#             )
#             # for rule in rules:
#             for rule in applicable_rules:
#                 # Find lines matching any category in the rule
#                 matching_lines = []
#                 total_qty = 0.0

#                 for categ in rule.categ_ids:
#                     for line in lines_by_category.get(categ.id, []):
#                         if line not in matching_lines:
#                             matching_lines.append(line)
#                             total_qty += line.product_uom_qty

#                 # Apply the rule to the matching lines
#                 for line in matching_lines:
#                     base_price = line.product_id.lst_price  # default to list price
#                     if rule.base == 'list_price':
#                         base_price = line.product_id.lst_price
#                     elif rule.base == 'standard_price':
#                         base_price = line.product_id.standard_price

#                     if rule.compute_price == 'fixed':
#                         line.price_unit = rule.fixed_price

#                     elif rule.compute_price == 'percentage':
#                         line.price_unit = base_price * (1 - (rule.percent_price / 100.0))

#                     elif rule.compute_price == 'formula':
#                         price = base_price

#                         # Apply discount
#                         if rule.price_discount:
#                             price = price * (1 - rule.price_discount)

#                         # Apply rounding
#                         if rule.price_round:
#                             price = round(price / rule.price_round) * rule.price_round

#                         # Apply surcharge
#                         price += rule.price_surcharge

#                         # Enforce min/max margins
#                         if rule.price_min_margin:
#                             price = max(price, base_price + rule.price_min_margin)
#                         if rule.price_max_margin:
#                             price = min(price, base_price + rule.price_max_margin)

#                         line.price_unit = price
#                     if total_qty < rule.min_quantity:
#                         line.price_unit = line.product_id.lst_price


# class ProductPriceListItem(models.Model):
#     _inherit = 'product.pricelist.item'

#     # Change categ_id from many2one to many2many
#     categ_ids = fields.Many2many(
#         'product.category',
#         'pricelist_item_category_rels',
#         'item_id', 'categ_id',
#         string='Catégories de produits',
#         help="Apply this rule to products in selected categories"
#     )

#     # Keep original categ_id for compatibility during migration
#     categ_id = fields.Many2one(
#         'product.category',
#         string='Product Category (Legacy)',
#         help="Legacy single category field - use Categories field instead"
#     )
#     compute_price = fields.Selection(
#         selection=[
#             ('fixed', "Fixed Price"),
#             ('percentage', "Discount"),
#             ('formula', "Formula"),
#         ],
#         index=True, default='percentage', required=True)

#     compute_pricing = fields.Selection(
#         selection=[
#             ('percentage', "Discount"),
#             ('fixed', "Fixed Price"),
#         ],
#         index=True, default='percentage', required=True, string="Calculer le prix")

#     applied_on = fields.Selection(
#         selection=[
#             ('3_global', "All Products"),
#             ('2_product_category', "Product Category"),
#             ('1_product', "Product"),
#             ('0_product_variant', "Product Variant"),
#         ],
#         string="Appliquer sur",
#         default='2_product_category',
#         required=True,
#         help="Pricelist Item applicable on selected option")

#     applied_on_categ = fields.Selection(
#         selection=[
#             ('2_product_category', "Catégories de produits"),
#         ],
#         string="Appliquer sur",
#         default='2_product_category',
#         required=True,
#         help="Pricelist Item applicable on selected option")

#     #=== COMPUTE METHODS ===#
#     @api.onchange('compute_pricing')
#     def onchange_compute_pricing(self):
#         self.compute_price = self.compute_pricing


#     #=== COMPUTE METHODS ===#
#     @api.onchange('applied_on_categ')
#     def onchange_applied_on_categ(self):
#         self.applied_on = self.applied_on_categ

#     @api.depends('applied_on', 'categ_id', 'product_tmpl_id', 'product_id', 'compute_price', 'fixed_price', \
#         'pricelist_id', 'percent_price', 'price_discount', 'price_surcharge')
#     def _compute_name_and_price(self):
#         for item in self:
#             if item.categ_id and item.applied_on == '2_product_category':
#                 item.name = _("Category: %s", item.categ_id.display_name)
#             if item.categ_ids and item.applied_on == '2_product_category':
#                 item.name = _("Category: %s", ', '.join(item.categ_ids.mapped('display_name')))
#             elif item.product_tmpl_id and item.applied_on == '1_product':
#                 item.name = _("Product: %s", item.product_tmpl_id.display_name)
#             elif item.product_id and item.applied_on == '0_product_variant':
#                 item.name = _("Variant: %s", item.product_id.display_name)
#             else:
#                 item.name = _("All Products")

#             if item.compute_price == 'fixed':
#                 item.price = formatLang(
#                     item.env, item.fixed_price, monetary=True, dp="Product Price", currency_obj=item.currency_id)
#             elif item.compute_price == 'percentage':
#                 item.price = _("%s %% discount", item.percent_price)
#             else:
#                 item.price = _("%(percentage)s %% discount and %(price)s surcharge", percentage=item.price_discount, price=item.price_surcharge)

#     @api.model
#     def create(self, vals):
#         """Handle data migration from old categ_id to new categ_ids"""
#         res = super().create(vals)
#         if vals.get('applied_on_categ', False):
#             vals['applied_on'] = vals.get('applied_on_categ')
#         return res

#     def write(self, vals):
#         """Handle data migration from old categ_id to new categ_ids"""
#         res = super().write(vals)
#         if vals.get('applied_on_categ', False):
#             vals['applied_on'] = vals.get('applied_on_categ')
#         return res

#     def _is_applicable_for(self, product, qty, date=None, **kwargs):
#         """Override to handle multiple categories with date parameter"""
#         if date is None:
#             date = fields.Date.context_today(self)

#         if self.applied_on == '2_product_category':
#             if not self.categ_ids:
#                 return False
#             # Check if product belongs to any of the selected categories
#             if product._name == 'product.product':
#                 return product.categ_id in self.categ_ids or product.categ_id.id == self.categ_id.id
#             return product.categ_id in self.categ_ids or product.categ_id.id == self.categ_id.id
#         return super()._is_applicable_for(product, qty, date=date, **kwargs)


# class ProductPriceList(models.Model):
#     _inherit = 'product.pricelist'

#     is_show_product_pricelist = fields.Boolean(
#         string='Show in product view',
#         default=False,
#         groups='product.group_sale_pricelist',
#         help='Enable to display this pricelist as a field in product and variant views'
#     )

#     display_position = fields.Selection(
#         [('after_price', 'After Sales Price'),
#          ('after_cost', 'After Cost Price'),
#          ('custom', 'Custom Position')],
#         string='Display Position',
#         default='after_price',
#         help='Determine where the pricelist field should appear in product views'
#     )

#     custom_position_field = fields.Char(
#         string='Anchor Field',
#         help='Specify the field name after which this pricelist should appear (for custom position)'
#     )

#     def _get_products_for_pricelist_item(self, item):
#         """Helper method to get products based on pricelist item scope"""
#         if item.applied_on == '3_global':
#             return self.env['product.template'].search([])
#         elif item.applied_on == '2_product_category':
#             if not item.categ_ids:
#                 return self.env['product.template']
#             return self.env['product.template'].search([('categ_id', 'in', item.categ_ids.ids)])
#         elif item.applied_on == '0_product_variant':
#             return item.product_id
#         return item.product_tmpl_id

#     def _get_model_info(self, is_variant=False):
#         """Return model-specific information based on variant flag"""
#         if is_variant:
#             return {
#                 'model': 'product.product',
#                 'inherit_id': self.env.ref('product.product_product_tree_view'),
#                 'model_id': self.env.ref('product.model_product_product').id,
#                 'prefix': 'variant_'
#             }
#         return {
#             'model': 'product.template',
#             'inherit_id': self.env.ref('product.product_template_tree_view'),
#             'model_id': self.env.ref('product.model_product_template').id,
#             'prefix': 'temp_'
#         }

#     def _create_or_update_field(self, model_info, pricelist_name):
#         """Create or update the dynamic field for the pricelist"""
#         field_name = f"x_{model_info['prefix']}{self.id}_{pricelist_name}"
#         field_description = f"{self.name} Price"

#         field = self.env['ir.model.fields'].search([
#             ('model_id', '=', model_info['model_id']),
#             ('name', '=', field_name)
#         ], limit=1)

#         if not field:
#             field = self.env['ir.model.fields'].sudo().create({
#                 'name': field_name,
#                 'field_description': field_description,
#                 'model_id': model_info['model_id'],
#                 'ttype': 'float',
#                 'store': True,
#                 'help': f"Automatically generated field for {self.name} pricelist"
#             })
#         return field

#     def _generate_view_arch(self, field_name, model_info):
#         """Generate the XML architecture for the dynamic view"""
#         position_field = {
#             'after_price': 'list_price',
#             'after_cost': 'standard_price',
#             'custom': self.custom_position_field or 'list_price'
#         }.get(self.display_position, 'list_price')

#         return f'''<?xml version="1.0"?>
#             <data>
#                 <field name="{position_field}" position="after"
#                     groups="product.group_sale_pricelist">
#                     <field name="{field_name}" optional="show"/>
#                 </field>
#             </data>'''

#     def _create_or_update_view(self, model_info, pricelist_name, field_name):
#         """Create or update the dynamic view for the pricelist"""
#         view_name = f'product.dynamic.fields.{pricelist_name}.{model_info["model"]}'

#         view = self.env['ir.ui.view'].search([
#             ('name', '=', view_name),
#             ('model', '=', model_info['model'])
#         ], limit=1)

#         arch_base = self._generate_view_arch(field_name, model_info)

#         if not view:
#             self.env['ir.ui.view'].sudo().create({
#                 'name': view_name,
#                 'type': 'tree',
#                 'model': model_info['model'],
#                 'mode': 'extension',
#                 'inherit_id': model_info['inherit_id'].id,
#                 'arch_base': arch_base,
#                 'active': True
#             })
#         else:
#             view.write({'arch_base': arch_base})

#     def _update_product_prices(self, item, products, field):
#         """Update product prices based on pricelist item"""
#         if item.compute_price == 'fixed':
#             products.write({field.name: item.fixed_price})
#         elif item.compute_price == 'percentage':
#             base_price = item.base == 'list_price' and 'list_price' or 'standard_price'
#             for product in products:
#                 price = product[base_price] * (1 - item.percent_price / 100)
#                 product.write({field.name: price})

#     def _cleanup_pricelist_artifacts(self, pricelist_name, model_info):
#         """Clean up views and fields when pricelist is deleted"""
#         views = self.env['ir.ui.view'].search([
#             ('name', '=', f'product.dynamic.fields.{pricelist_name}.{model_info["model"]}'),
#             ('model', '=', model_info['model'])
#         ])
#         views.unlink()

#         field_name = f"x_{model_info['prefix']}{self.id}_{pricelist_name}"
#         self.env['ir.model.fields'].search([
#             ('model_id', '=', model_info['model_id']),
#             ('name', '=', field_name)
#         ]).unlink()

#     def check_pricelist_condition(self):
#         """Main method to update pricelist display and pricing"""
#         if not self.item_ids:
#             return

#         pricelist_name = self.name.replace(" ", "_")

#         for item in self.item_ids:
#             is_variant = item.applied_on == '0_product_variant'
#             products = self._get_products_for_pricelist_item(item)
#             model_info = self._get_model_info(is_variant)

#             field = self._create_or_update_field(model_info, pricelist_name)
#             self._create_or_update_view(model_info, pricelist_name, field.name)
#             self._update_product_prices(item, products, field)

#     @api.model
#     def create(self, vals):
#         """Override create to handle pricelist display setup"""
#         pricelist = super().create(vals)
#         if pricelist.is_show_product_pricelist:
#             pricelist.check_pricelist_condition()
#         return pricelist

#     def write(self, vals):
#         """Override write to handle pricelist display updates"""
#         res = super().write(vals)
#         if 'is_show_product_pricelist' in vals or 'display_position' in vals or 'custom_position_field' in vals:
#             self.check_pricelist_condition()
#         return res

#     def unlink(self):
#         """Clean up dynamic fields and views before deletion"""
#         for pricelist in self:
#             pricelist_name = pricelist.name.replace(" ", "_")

#             # Clean up variant artifacts
#             variant_info = self._get_model_info(is_variant=True)
#             self._cleanup_pricelist_artifacts(pricelist_name, variant_info)

#             # Clean up template artifacts
#             template_info = self._get_model_info(is_variant=False)
#             self._cleanup_pricelist_artifacts(pricelist_name, template_info)

#         return super().unlink()

#     @api.constrains('custom_position_field')
#     def _check_custom_position_field(self):
#         """Validate the custom position field exists"""
#         for pricelist in self:
#             if pricelist.display_position == 'custom' and not pricelist.custom_position_field:
#                 raise ValidationError(_("Please specify an anchor field for custom position display."))
