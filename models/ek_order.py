from odoo import models, fields, api, _, exceptions
import logging
import json
import requests
from datetime import datetime
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from odoo.exceptions import ValidationError, UserError
from odoo.http import request
_logger = logging.getLogger(__name__)
from .config import *


class EkOrder(models.Model):
    _inherit = 'sale.order'


    create_by = fields.Char('Crée a partir de', default='Odoo')
    ek_file = fields.Char("Dossier ekiclik")
    ek_state = fields.Char("Statut ekiclik")
    cancel_reason = fields.Char("Motif d'annulation de dossier")

    headers = {"Content-Type": "application/json","Accept": "application/json", "Catch-Control": "no-cache"}

    @api.model
    def create(self, vals):

        # SET THE ENVIRONMENT
        utils = self.env['odoo_utils']
        domain = "https://apiadmin-alsalam-stg.wissal-group.com"

        # RECEIVE ORDER/QUOTATION FROM EK
        if 'create_by' in vals and vals['create_by'] != 'odoo':

            # SEARCH FOR THE CLIENT
            if "client" in vals:
                if vals["client"]:
                    client = vals.get('client', {})
                vals.pop('client')
                try:
                    client_id = self.env['res.partner'].search([('name', '=', client["name"])])
                    if client_id:
                        vals['partner_id'] = client_id.id
                    else:
                        # CHECK TYPE OF CLIENT IF PERSON
                        if client["is_company"] == False:
                            _logger.info(
                                '\n\n\n company\n\n\n\n--->>  %s\n\n\n\n', client['is_company'])
                            if 'type' in client and client['type'] == 'delivery':

                                # PUT THE PARENT ID BY SEARCHING WITH SOURCE
                                if 'source' in client and client['source']:
                                    # Get the bank record
                                    bank = self.env['res.partner'].search([('name', '=', client['source'])])
                                    if bank:
                                        client['parent_id'] = bank.id
                                    else:
                                        bank = self.env['res.partner'].create([{'name': client['source']}])
                                        client['parent_id'] = bank.id

                                    client.pop('source')

                                # PUT THE country_id [res.country] (Many2one Relation)
                                if 'country_id' in client.keys():
                                    country = self.env['res.country'].search([('code', '=', client['country_id'])])

                                    client['country_id'] = country.id
                                # PUT THE state_id [res.country.state] (Many2one Relation)
                                if 'state_id' in client.keys():
                                    state_id = utils.affect_many_to_one(
                                        client['state_id'], 'res.country.state', 'name')
                                    if state_id:
                                        client['state_id'] = state_id
                                    else:
                                        client['state_id'] = None

                        _logger.info(
                            '\n\n\ncreating partner\n\n\n\n--->>  %s\n\n\n\n', client)
                        partner = self.env['res.partner'].create({
                            'name': client['name'],
                            'email': client['email'],
                            'type': client['type'],
                            'source': client['parent_id'],
                            'state_id': client['state_id'],
                            'country_id': client['country_id'],
                            'phone': client['phone'],
                            'is_company': client['is_company'],
                            'parent_id': client['parent_id']
                        })

                        _logger.info(
                            '\n\n\npartner created \n\n\n\n--->>  %s\n\n\n\n', client)
                        vals['partner_id'] = partner.id

                except Exception as e:
                    _logger.error("An error occurred: %s", e)
                    raise

            vals['create_by'] = "ekiclik"

            logging.warning("DATA TO CREATE======")
            logging.warning(vals)
            if 'order_line' in vals:
                order_line_values = vals.get('order_line', {})
                vals.pop('order_line')

            rec = super(EkOrder, self).create(vals)
            product = None

            if order_line_values:
                for line in order_line_values:
                    # Get the product record based on default_code
                    if 'default_code' in line:
                        product = self.env['product.product'].search(
                            [('default_code', '=', line['default_code'])])

                    if product:
                        order_values = {
                            'product_id': product.id,
                            'product_uom_qty': line['qty'],
                            'name': rec.name,
                            'product_uom': product.uom_id.id,
                            'state': 'sale',
                            'price_unit': product.list_price,
                            'order_id': rec.id
                        }
                        self.env['sale.order.line'].create(order_values)

                    else:
                        new_product = self.env['product.product'].create({
                            'name': line['product_name'],
                            'default_code': line['default_code']
                        })

                        if new_product:
                            order_values = {
                                'product_id': new_product.id,
                                'product_uom_qty': line['qty'],
                                'name': rec.name,
                                'product_uom': new_product.uom_id.id,
                                'state': 'sale',
                                'price_unit': product.list_price,
                                'order_id': rec.id

                            }
                            self.env['sale.order.line'].create(order_values)
            rec.action_confirm()
            return rec
        else:
            return super(EkOrder, self).create(vals)

    def write(self, vals):

        # SET THE ENVIRONMENT
        utils = self.env['odoo_utils']
        domain = "https://apiadmin-alsalam-stg.wissal-group.com"

        # RECEIVE ORDER/QUOTATION FROM EK
        if 'create_by' in vals and vals['create_by'] != 'odoo':
            try:
                if 'ek_state' in vals and vals['ek_state']:
                    if vals['ek_state'] == "EK_ORDER_IN_PREPARATION":
                        vals['ek_state'] = "Commande en préparation"
                    if vals['ek_state'] == "EK_ORDER_IN_DELIVERY":
                        vals['ek_state'] = "Livraison en cours"
                    if vals['ek_state'] == "EK_ORDER_DELIVERED":
                        vals['ek_state'] = "Client livré"
                    if vals['ek_state'] == "EK_CLIENT_ORDER_CANCELED":
                        vals['ek_state'] = "Commande annulée"
                        self.action_cancel()

                vals['create_by'] = "ekiclik"

                return super(EkOrder, self).write(vals)

            except Exception as e:
                _logger.error("An error occurred: %s", e)
                raise

        else:
            return super(EkOrder, self).write(vals)
