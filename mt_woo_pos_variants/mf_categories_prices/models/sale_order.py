import logging
from odoo import models, fields, api, exceptions

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

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

        categ_config_amount = self.env['order.line.category.price'].search([('categ_ids', 'in', sol.product_id.categ_id.ids), ('qty', '=', quantity)], limit=1).amount
        if categ_config_amount:
            sol.price_unit = categ_config_amount
        return sol.price_unit


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.onchange('product_uom_qty', 'product_id')
    def onchange_product_quantity(self):
        categ_config_amount = self.env['order.line.category.price'].search([('categ_ids', 'in', self.product_id.categ_id.ids), ('qty', '=', self.product_uom_qty)], limit=1).amount
        if categ_config_amount:
            self.price_unit = categ_config_amount / self.product_uom_qty
