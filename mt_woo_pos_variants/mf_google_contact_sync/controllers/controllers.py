import json
import werkzeug
from odoo import http
from odoo.http import request
from google_auth_oauthlib.flow import Flow


class GoogleContactsApiAccess(http.Controller):
    @http.route('/response', auth='public')
    def get_response(self, **kwargs):
        try:
            # Check if the required parameters are present
            state, code, scope = kwargs.get('state'), kwargs.get('code'), kwargs.get('scope')
            if not (state and code and scope):
                return ("<div><h3 style='display: flex;justify-content: center;align-items: center;height:80vh;'>"
                        "<b>Not a valid google response</b></h3></div>")

                config = request.env['ir.config_parameter'].sudo()
                SCOPES = ['https://www.googleapis.com/auth/contacts']
                web_url = config.get_param('web.base.url')
                mf_google_contact_credentials = config.get_param('mf_google_contact_credentials')

                # Initialize the OAuth flow
                flow = Flow.from_client_config(json.loads(mf_google_contact_credentials), SCOPES,
                                           redirect_uri=f"{web_url}/response")
                # Construct the authorization URL
                url = f"{web_url.replace('http', 'https')}/response?state={state}&code={code}&scope={scope.replace('/', '%2F').replace(':', '%3A')}"
                try:
                    # Fetch the token using the authorization response URL
                    flow.fetch_token(authorization_response=url)
                except Exception:
                    # Handle Google server error
                        return ("<div><h3 style='display: flex;justify-content: center;align-items: center;height:80vh;'>"
                                "<div><b>Google Server Error</b><br/>Authorize again</h3></div></div>")

            # Save the token in the configuration
            config.set_param('mf_google_contact_tokens', flow.credentials.to_json())
            # Redirect to the web interface
            return werkzeug.utils.redirect('/web/')
        except Exception as e:
            # Handle internal server error
            if 'Google Server Error</b><br/>Authorize again' in str(e):
                return e
            return ("<div><h3 style='display: flex;justify-content: center;align-items: center;height:80vh;'>"
                    "<b>Internal Server Error</b></h3></div>")
