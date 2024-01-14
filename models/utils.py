from odoo import models
import psycopg2
import logging

_logger = logging.getLogger(__name__)

class Utils(models.Model):
    _name = 'odoo_utils'
    _description = 'Common useful functions (This class is used to avoid duplicated code)'

    # FUNCTION TO QUERY THE FIELDs FROM A MODEL
    def affect_many_to_one(self, request_key, object, field_in_db, field_to_get = 'id'):
        field = self.env[object].search([(field_in_db, '=', request_key)])[field_to_get]
        if field:
            return field
        else:
            return False
        
        
    # Function to connect to EK DB and get sequences
    def _ekconnect(self):
        ###################### dev

        return psycopg2.connect(host="3.9.25.94",
                                user="slmsg",
                                options='',
                                port="6432",
                                dbname="dbsalamsg",
                                password="W0G_ACt$8lO5",)
                                # sslmode='require')
        
    def order_affect_address(self, client_env):

        partner = self.env['res.partner'].search([('id', '=', client_env)])
        name = partner.name
        email = partner.email
        if partner.is_company == False:

            delivery_address_list = []
            # Fill shiping address fields (if partner is person)
            for child in partner.child_ids:
                if child.type == 'delivery':
                    delivery_address = {}
                    state = child.state_id.name if child.state_id.name else ""
                    city =  child.city if child.city else ""
                    street = child.street if child.street else ""
                    combined_key = state + city + street
                    
                    delivery_address['lastname'] = partner.lastname
                    delivery_address['name'] = partner.name
                    delivery_address['phone'] = partner.phone
                    delivery_address['type'] = child.type
                    delivery_address['combined_keys'] = combined_key
                    delivery_address['parent_id'] = email
                    delivery_address['street'] = child.street
                    delivery_address['street2'] = child.street2
                    delivery_address['zip'] = child.zip       
                    state = self.affect_many_to_one(child.state_id.id, 'res.country.state', 'id', 'name')
                    delivery_address['city'] = state
                    country_code = self.affect_many_to_one(child.country_id.id, 'res.country', 'id', 'code')
                    delivery_address['country_id'] = country_code
                    delivery_address_list.append(delivery_address)
            if not delivery_address_list:
                delivery_address = {}
            else:
                delivery_address = delivery_address_list[-1]

            if partner.parent_id:
                parent = partner.parent_id
                parent_siret = parent.siret

                # Fill invoice address fields if parent company exist
                invoice_address = {}
                for child in parent.child_ids:
                    if child.type == 'invoice':
                        invoice_address['name'] = parent.name
                        invoice_address['phone'] = parent.phone
                        invoice_address['street'] = child.street
                        invoice_address['street2'] = child.street2
                        invoice_address['zip'] = child.zip
                        invoice_address['state_id'] = child.city
                        state = self.affect_many_to_one(child.state_id.id, 'res.country.state', 'id', 'name')
                        invoice_address['city'] = state
                        country_code = self.affect_many_to_one(child.country_id.id, 'res.country', 'id', 'code')
                        invoice_address['country_id'] = country_code
            else:

                # Fill invoice address fields if partner is person and no parent company
                parent_siret = None
                invoice_address = delivery_address
        else:

            # Fill invoice address fields if partner is company
            invoice_address = {}
            for child in partner.child_ids:
                if child.type == 'invoice':
                    invoice_address['name'] = name
                    invoice_address['phone'] = partner.phone
                    invoice_address['street'] = child.street
                    invoice_address['street2'] = child.street2
                    invoice_address['zip'] = child.zip
                    invoice_address['state_id'] = child.city
                    state = self.affect_many_to_one(child.state_id.id, 'res.country.state', 'id', 'name')
                    invoice_address['city'] = state
                    country_code = self.affect_many_to_one(child.country_id.id, 'res.country', 'id', 'code')
                    invoice_address['country_id'] = country_code
            delivery_address = invoice_address
            parent_siret = None
        return {
                'invoice_address':invoice_address, 
                'delivery_address':delivery_address, 
                'parent_siret':parent_siret, 
                'email':email,
                'name':name
                }
