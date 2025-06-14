# -*- coding: utf-8 -*-
import logging

from woocommerce import API
from odoo.exceptions import UserError, MissingError
from odoo import models, api, fields, _
from odoo.tools import config
from bs4 import BeautifulSoup
config['limit_time_real'] = 10000000
config['limit_time_cpu'] = 600


_logger = logging.getLogger(__name__)


class WooCommerceProductImages(models.Model):
    _name = 'woocommerce.product.image'
    _description = 'WooCommerce Product Images'
    _order = "wooc_id desc"

    wooc_id = fields.Char(string="WooCommerce id")
    name = fields.Char(string="WooCommerce image Name")
    wooc_url = fields.Char(string="Image URL")
    image = fields.Image(string="Add New Image")
    wooc_image = fields.Binary(string="WooCommerce Image")

    is_image_synced = fields.Boolean(default=False, string="Image Synced")
    is_variation_update = fields.Boolean(default=False, string="Variation Update")
    is_import_image = fields.Boolean(default=False, string="Is Import Images")
    is_main_image = fields.Boolean(default = False, string="Set as Main Image")

    product_image_variant_ids = fields.One2many("product.product", "wooc_product_image_id",domain="[('product_tmpl_id', '=', product_template_id),('wooc_product_image_id', '=', False )]")
    product_template_id = fields.Many2one('product.template', string='Product template', ondelete='cascade')
    woo_product_variant_id = fields.Many2one('woocommerce.product.variant', domain="[('product_template_id', '=', product_template_id)]")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals['wooc_image']:
                raise UserError(_("Please attach a image!!!"))

            new_vals = super(WooCommerceProductImages, self).create(vals)
            if new_vals['product_template_id']:
                product_template_id = new_vals['product_template_id']

            is_import_image = new_vals['is_import_image']

        self.env.cr.commit()
        # _logger.error('///////////////////||||||||||')
        # _logger.error(is_import_image)
        if product_template_id and not is_import_image:
            self.wooc_create_product_image(product_template_id)

    def write(self, vals):
        _logger.info('\n\n\n\n Image Updating \n\n\n\n\n')
        is_import_image = False
        is_update_only = False
        is_position_update = False

        # need to check condition for update image and change variation together
        if vals.__contains__('is_import_image'):
            is_import_image = vals['is_import_image']
            del vals['is_import_image']

        if vals.__contains__('update_only'):
            is_update_only = vals['update_only']
            del vals['update_only']

        if vals.__contains__('wooc_image') and not is_import_image  and not self.env.context.get("dont_send_data_to_wooc_from_write_method"):
            vals['is_image_synced'] = False
            vals['wooc_id'] = False
            
        if vals.__contains__('is_main_image') and not is_import_image  and not self.env.context.get("dont_send_data_to_wooc_from_write_method"):
            if vals['is_main_image']:
                is_position_update = True
                self._cr.execute("""UPDATE woocommerce_product_image SET is_main_image = False WHERE product_template_id = '%s'""" % (self.product_template_id.id))
       
        if vals.__contains__('product_image_variant_ids') and not is_import_image and not self.env.context.get("dont_send_data_to_wooc_from_write_method"):
            # remove old variant image

            vals['is_image_synced'] = True
            vals['is_variation_update'] = True
            new_data = {"update": [], }
            p_id_list = self.env['product.product'].sudo().search_read([('product_tmpl_id', '=', self.product_template_id.id)],['woocomm_variant_id'])              
                
            for change_id in vals['product_image_variant_ids']:
                                        
                for dict_ in [x for x in p_id_list if x["id"] == change_id[1]]:
                    variant_wooc_id = dict_['woocomm_variant_id']
                    
                if change_id[0] == 3:
                    new_data["update"].append({"id": variant_wooc_id,"image": {}  })
                    
                if change_id[0] == 4 and not vals.__contains__('wooc_image'):
                    new_data["update"].append({"id": variant_wooc_id,"image": {"id" : self.wooc_id}  })

            self.wooc_variant_image_bulk_update(self.product_template_id, new_data)
                
        super(WooCommerceProductImages, self).write(vals)
        self.env.cr.commit()

        if not is_import_image and not is_update_only and not self.env.context.get("dont_send_data_to_wooc_from_write_method"):
            self.wooc_create_product_image(self.product_template_id, is_position_update)
            
    def unlink(self):
        new_data = {"update": [], }
        
        for img_rec in self:
            product_template_id = img_rec['product_template_id']          

            for var_img in img_rec.product_image_variant_ids:
                new_data["update"].append({"id": var_img.woocomm_variant_id,"image": {}  })
            
            super(WooCommerceProductImages, img_rec).unlink()

        self.wooc_variant_image_bulk_update(product_template_id, new_data)

        woo_api = self.init_wc_api(product_template_id.woocomm_instance_id)
        data, id_list = self.wooc_get_image_list(product_template_id)
        del_img_update = woo_api.put("products/%s" % (product_template_id.wooc_id), data)

        if del_img_update.status_code == 200:
            _logger.info('\n\n\n\n Image Successfully Deleted \n\n\n\n\n')
        else:
            _logger.info('\n\n\n\n Error Deleting Images: -- %s \n\n\n\n\n' % del_img_update.json())

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

    def wooc_create_product_image(self, product_template_id, image_position_update = False):
        
        if not product_template_id.wooc_id:
            return
        _logger.error(f'//////////////////////////////////////{product_template_id} {product_template_id.wooc_id} {image_position_update}')
        wooc_image_list = {"images": [], }
        id_list = []
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        woo_api = self.init_wc_api(product_template_id.woocomm_instance_id)
        image_list_not_synced = self.sudo().search([('product_template_id', '=', product_template_id.id), ('is_image_synced', '=', False)])
        wooc_image_list, id_list = self.wooc_get_image_list(product_template_id)
        product_wooc_id = str(product_template_id.wooc_id)
       
        #only to update if the image position changed
        if image_position_update and len(image_list_not_synced) == 0 :
            _logger.error(f'(((((((((((((((((( image_position_update')
            img_update = woo_api.put("products/%s" %(product_wooc_id), wooc_image_list)
        
        for img in image_list_not_synced:
            new_data = {"images": [], "verify_ssl": False}
            new_data['images'] = wooc_image_list['images'].copy()

            src = base_url + "/woocomm/images/" + str(img['id']) + "/" + str(img['name'])
            new_data['images'].append({'src': src})

            _logger.error(f'new_data ==> {new_data}')
            img_update = woo_api.put("products/%s" %(product_wooc_id), new_data)
            _logger.error(f'img_update ==> {img_update}')

            if img_update.status_code == 400:
                _logger.info('\n\n\n\n 400 Error: -- %s \n\n\n\n\n' % img_update.json())

            if img_update.status_code == 200:
                img_update_json = img_update.json()

                for image in img_update_json['images']:
                    if image['id'] not in id_list:
                        new_image_update = self.sudo().search([('id', '=', img.id), ('product_template_id.woocomm_instance_id', '=', product_template_id.woocomm_instance_id.id)])
                        new_image_update.write({'wooc_id': image['id'], 'is_image_synced': True, "update_only": True})
                        wooc_image_list['images'].append({'id': image['id']})
                        id_list.append(image['id'])

                        new_data = {"update": [], }
                        for var_img in img.product_image_variant_ids:
                            new_data["update"].append({"id": var_img.woocomm_variant_id,"image": {"id" : image['id']}  })
                        self.wooc_variant_image_bulk_update(product_template_id, new_data)                        

                        self.env.cr.commit()
                        break

    def wooc_variant_image_update(self, product_template_id, img_id, product_variant_id):
        woo_api = self.init_wc_api(product_template_id.woocomm_instance_id)
        if img_id:
            var_img = {"image": {'id': img_id}, }
        else:
            var_img = {"image": {}, }

        img_update = woo_api.put("products/%s/variations/%s" % (str(product_template_id.wooc_id), product_variant_id.woocomm_variant_id), var_img)
        return

    def wooc_variant_image_bulk_update(self, product_template_id, image_data):
        woo_api = self.init_wc_api(product_template_id.woocomm_instance_id)

        img_update = woo_api.put("products/%s/variations/batch" % (str(product_template_id.wooc_id)), image_data)
        return

    def wooc_get_image_list(self, product_template_id):
        wooc_image_list = {"images": [], }
        id_list = []
        woo_api = self.init_wc_api(product_template_id.woocomm_instance_id)

        exist_img_rec = self.sudo().search([('product_template_id', '=', product_template_id.id), ('wooc_id', '!=', False), ('product_template_id.woocomm_instance_id', '=', product_template_id.woocomm_instance_id.id)])
        exist_img_ids = exist_img_rec.mapped('wooc_id')
        
        #to get the {wooc_id:is_main_image} dictionary 
        is_mainimage_list = dict(map(lambda sub: (sub.wooc_id, sub.is_main_image), exist_img_rec))
        
        product = woo_api.get("products/%s" %(str(product_template_id.wooc_id)))
        if product.status_code == 200:
            product = product.json()

            for image in product['images']:
                if str(image['id']) in exist_img_ids:
                    if is_mainimage_list[str(image['id'])]:
                        wooc_image_list['images'].insert(0, {'id': image['id']})
                    else:  
                        wooc_image_list['images'].append({'id': image['id']})
                        
                    id_list.append(int(image['id']))

        return wooc_image_list, id_list
