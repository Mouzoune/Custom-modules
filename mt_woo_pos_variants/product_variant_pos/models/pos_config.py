# Copyright (C) Softhealer Technologies.
# -*- coding: utf-8 -*-

from odoo import api, models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    product_variant_qty_available_count = fields.Integer(
        '# Product Variants Available Quantity', compute='_compute_product_variant_qty_available_count')

    @api.depends('product_variant_ids.product_tmpl_id')
    def _compute_product_variant_qty_available_count(self):
        for template in self:
            template.product_variant_qty_available_count = len(template.product_variant_ids.filtered(lambda x: x.qty_available))

class PosConfig(models.Model):
    _inherit = 'pos.config'

    sh_pos_enable_product_variants = fields.Boolean(
        string='Enable Product Variants')
    sh_close_popup_after_single_selection = fields.Boolean(
        string='Auto close popup after single variant selection')
    sh_pos_display_alternative_products = fields.Boolean(
        string='Display Alternative product')
    sh_pos_variants_group_by_attribute = fields.Boolean(
        string='Group By Attribute', default=False)


class ProductTemplateInherit(models.Model):
    _inherit = 'product.template'

    sh_alternative_products = fields.Many2many(
        'product.product', 'sh_table_pos_alternative_products', string='Alternative Products', domain="[('available_in_pos', '=', True)]")
