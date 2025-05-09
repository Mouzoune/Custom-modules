
import io
import json
from odoo import http
from odoo.http import Controller, route, request
from odoo.tools import html_escape
from base64 import b64decode
from odoo.tools.image import image_data_uri, base64_to_image
import logging

_logger = logging.getLogger(__name__)

                                                
class ImageController(http.Controller):        
    @http.route('/woocomm/images/<int:id>/<name>', type='http', auth='public', methods=['GET'], csrf=False)
    def get_woocomm_data(self, id, name):
        _logger.error('/////////////////////////////====/')
        _logger.error(id)
        _logger.error(name)
        if name == 'wooc_variant_image':
            image = http.request.env['woocommerce.product.variant'].sudo().search([('id', '=', id)], limit=1)
            # _logger.error(image.wooc_variant_image)
            raw_image = base64_to_image(image.wooc_variant_image)

            return http.Response(response=b64decode(image.wooc_variant_image.decode("utf-8")),
                                 status=200,
                                 content_type=self.get_image_type(raw_image.format)
                                 )
        else:
            image = http.request.env['woocommerce.product.image'].sudo().search([('id', '=', id)], limit=1)
            raw_image = base64_to_image(image.wooc_image)
            resp = http.Response(response = b64decode(image.wooc_image.decode("utf-8")),
                                 status=200,
                                 content_type=self.get_image_type(raw_image.format)
                                 )
            _logger.error(resp)
            return
    
    def get_image_type(self, img_type):
        
        image_type = {
                    "JPEG"  : "image/jpeg",
                    "PNG"   : "image/png",
                    }
        if(image_type.__contains__(img_type)):
            return image_type[img_type]
        else:
            return "image/png"
