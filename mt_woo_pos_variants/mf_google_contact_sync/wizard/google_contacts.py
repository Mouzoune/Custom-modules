from __future__ import print_function
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from odoo import models, fields, exceptions, _
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from odoo.exceptions import UserError
import logging
import requests
import base64
import json

_logger = logging.getLogger(__name__)


class GoogleContactsSync(models.TransientModel):
    _name = 'google.contacts.sync'

    name = fields.Char('Name')
    email = fields.Char('Email')
    phone = fields.Char('Phone Number')
    mobile = fields.Char('Mobile Number')
    object = fields.Char('Object')

    # current_user = fields.Many2one('res.users', 'Current User', default=lambda self: self.env.user)

    def sync_google_contacts(self, kwargs=None):
        SCOPES = ['https://www.googleapis.com/auth/contacts']
        conf = self.env['ir.config_parameter'].sudo()
        web_url = conf.get_param('web.base.url')
        mf_google_contact_credentials = conf.get_param('mf_google_contact_credentials')
        mf_google_contact_tokens = conf.get_param('mf_google_contact_tokens')
        self.search([]).unlink()
        creds = None

        if mf_google_contact_credentials in [False, None, '']:
            raise exceptions.MissingError("Credentials Required.")

        if mf_google_contact_tokens not in [False, None, '']:
            json_creds = json.loads(mf_google_contact_tokens)
            creds = Credentials.from_authorized_user_info(json_creds, SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_config(json.loads(mf_google_contact_credentials),
                                                           SCOPES, redirect_uri=web_url + "/response")
                auth_url, _ = flow.authorization_url(prompt='consent')
                return {
                    "url": auth_url,
                    "type": "ir.actions.act_url"
                }
        try:
            service = build('people', 'v1', credentials=creds)

            people = service.people().connections()
            people_list = people.list(resourceName='people/me', pageSize=25,
                                      personFields='names,emailAddresses,phoneNumbers,photos,urls')
            while people_list is not None:
                results = people_list.execute()

                connections = results.get('connections', [])
                for contact in connections:
                    name = contact['names'][0]['displayName'] if 'names' in contact else 'N/A'
                    email = contact['emailAddresses'][0]['value'] if 'emailAddresses' in contact else 'N/A'
                    phone = contact['phoneNumbers'][0]['value'] if 'phoneNumbers' in contact else 'N/A'
                    mobile = 'N/A'
                    if len(contact['phoneNumbers']) > 1:
                        mobile = contact['phoneNumbers'][1]['value'] if 'phoneNumbers' in contact else 'N/A'
                    self.create({
                        'name': name,
                        'email': email,
                        'phone': phone,
                        'mobile': mobile,
                        'object': json.dumps(contact),
                    })

                people_list = people.list_next(people_list, results)

            return {
                'name': "Your contacts",
                'view_mode': 'tree',
                'view_id': self.env.ref('google_contact_sync.view_contacts_tree').id,
                'res_model': 'google.contacts.sync',
                'type': 'ir.actions.act_window',
                'target': 'new',
            }
        except HttpError as e:
            _logger.info("HttpError :: " + str(e.__dict__))
        except Exception as e:
            _logger.info("Exception :: " + str(e.__dict__))

    def import_contacts(self):
        try:
            for rec in self:
                contact = self.env['res.partner'].search([('phone', '=', rec.phone)])
                google_response = json.loads(rec.object)
                values = {
                    'company_type': 'person',
                    'name': rec.name,
                    'email': rec.email,
                    'phone': rec.phone,
                }
                if google_response.get('photos') and len(google_response.get('photos')):
                    values['image_1920'] = base64.b64encode(requests.get(google_response['photos'][0]['url']).content)

                if google_response.get('urls') and len(google_response.get('urls')):
                    values['website'] = google_response['urls'][0]['value']

                contact.update(values) if contact.id else contact.create(values)
        except Exception as e:
            raise exceptions.ValidationError(e.__dict__)