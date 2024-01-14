# Echange Odoo-Ekiclik
## Description
This project aims to establish seamless connectivity and real-time synchronization between Odoo and the Ekiclik platform.
The Odoo database serves as the centralized hub for data from the collaborating banks.

The exchange is facilitated through REST APIs, enabling a smooth, easy, and secure interaction between the two platforms.
The REST APIs ensure a seamless flow of information, fostering efficient and secure communication,
enhancing collaboration, and supporting the centralized management of data across diverse banking entities.

## Principal modules
* Product catalog
    * Categories
    * Products
    * Configurations
* Stock
    * Update stocks
    * Points of sales
    * Orders
    * Purchase
    * Invoicing & receipts 
* Clients
* Users
* CRM

### Modules managed by Odoo only
* Stock
  * Update quantities (purchase & order)

### Modules managed by EKICLIK only
* Client
* Users
* POS


### Modules managed by both Odoo and EKICLIK
* Product
* Stock
* Categories




# Odoo REST API

This is a module which expose Odoo as a REST API

## Installing

* Download this module and put it to your Odoo addons directory
* Install requirements with `pip install -r requirements.txt`

## Getting Started

### Authenticating users

Before making any request make sure to login and obtain session_id(This will act as your Authentication token), Send all
your requests with session_id as a parameter for authentication. There are two ways to obtain `session_id`, the first
one is using `/web/session/authenticate/` route and the second one is using `/auth/` route.

- Using `/web/session/authenticate/` route

  Send a POST request with JSON body as shown below.

  `POST /web/session/authenticate/`

  Request Body

  ```js
  {
      "jsonrpc": "2.0",
      "params": {
          "login": "your@email.com",
          "password": "your_password",
          "db": "database_name"
      }
  }
  ```

  Obtain `session_id` from a cookie created(Not the one from a response). It'll be a long string something like "
  62dd55784cb0b1f69c584f7dc1eea6f587e32570", Then you can use this as a parameter to all requests.

- Using `/auth/` route

  If you have set the default database th
- en you can simply use `/auth` route to do authentication as

  `POST /auth/`

  Request Body

  ```js
  {
      "params": {
          "login": "your@email.com",
          "password": "your_password",
          "db": "your_db_name"
      }
  }
  ```

  Use `session_id` from the response as a parameter to all requests.

**Note:** For security reasons, in production don't send `session_id` as a parameter, use a cookie instead.

### Examples showing how to obtain `session_id` and use it

<details>
<summary>
Using <code>/web/session/authenticate/</code> route for authentication
</summary>

```py
import json
import requests
import sys

AUTH_URL = 'http://localhost:8069/web/session/authenticate/'
headers = {'Content-type': 'application/json'}
# Remember to configure default db on odoo configuration file(dbfilter = ^db_name$)
# Authentication credentials
data = {
    'params': {
        'login': 'your@email.com',
        'password': 'yor_password',
        'db': 'your_db_name'
    }
}
# Authenticate user
res = requests.post(
    AUTH_URL,
    data=json.dumps(data),
    headers=headers
)
# Get session_id from the response cookies
# We are going to use this as our API key
session_id = res.cookies.get('session_id', '')
# Example 1
# Get users
USERS_URL = 'http://localhost:8069/api/res.users/'
# Pass session_id for auth
# This will take time since it retrives all res.users fields
# You can use query param to fetch specific fields
params = {'session_id': session_id}
res = requests.get(
    USERS_URL,
    params=params
)
# This will be a very long response since it has many data
print(res.text)
# Example 2
# Get products(assuming you have products in you db)
# Here am using query param to fetch only product id and name(This will be faster)
USERS_URL = 'http://localhost:8069/api/product.product/'
# Pass session_id for auth
params = {'session_id': session_id, 'query': '{id, name}'}
res = requests.get(
    USERS_URL,
    params=params
)
# This will be small since we've retrieved only id and name
print(res.text)
```

</details>


<details>
<summary>
Using <code>/auth/</code> route for authentication
</summary>

```py
import json
import requests

AUTH_URL = 'http://localhost:8069/auth/'
headers = {'Content-type': 'application/json'}
# Remember to configure default db on odoo configuration file(dbfilter = ^db_name$)
# Authentication credentials
data = {
    'params': {
        'login': 'your@email.com',
        'password': 'yor_password',
        'db': 'your_db_name'
    }
}
# Authenticate user
res = requests.post(
    AUTH_URL,
    data=json.dumps(data),
    headers=headers
)
# Get session_id from the response
# We are going to use this as our API key
session_id = json.loads(res.text)['result']['session_id']
# Example 1
# Get users
USERS_URL = 'http://localhost:8069/api/res.users/'
# Pass session_id for auth
# This will take time since it retrives all res.users fields
# You can use query param to fetch specific fields
params = {'session_id': session_id}
res = requests.get(
    USERS_URL,
    params=params
)
# This will be a very long response since it has many data
print(res.text)
# Example 2
# Get products(assuming you have products in you db)
# Here am using query param to fetch only product id and name(This will be faster)
USERS_URL = 'http://localhost:8069/api/product.product/'
# Pass session_id for auth
params = {'session_id': session_id, 'query': '{id, name}'}
res = requests.get(
    USERS_URL,
    params=params
)
# This will be small since we've retrieved only id and name
print(res.text)
```

</details>

<details>
<summary>
Avoiding to send <code>session_id</code> as a parameter for security reasons
</summary>

When authenticating users, you can use a cookie instead of sending `session_id` as a parameter, this method is
recommended in production for security reasons, below is the example showing how to use a cookie.

```py
import json
import requests
import sys

AUTH_URL = 'http://localhost:8069/web/session/authenticate/'
headers = {'Content-type': 'application/json'}
# Remember to configure default db on odoo configuration file(dbfilter = ^db_name$)
# Authentication credentials
data = {
    'params': {
        'login': 'your@email.com',
        'password': 'yor_password',
        'db': 'your_db_name'
    }
}
# Authenticate user
res = requests.post(
    AUTH_URL,
    data=json.dumps(data),
    headers=headers
)
# Get response cookies
# We will use this to authenticate user
cookies = res.cookies
# Example 1
# Get users
USERS_URL = 'http://localhost:8069/api/res.users/'
# This will take time since it retrives all res.users fields
# You can use query param to fetch specific fields
res = requests.get(
    USERS_URL,
    cookies=cookies  # Here we are sending cookies instead of `session_id`
)
# This will be a very long response since it has many data
print(res.text)
# Example 2
# Get products(assuming you have products in you db)
# Here am using query param to fetch only product id and name(This will be faster)
USERS_URL = 'http://localhost:8069/api/product.product/'
# Use query param to fetch only id and name
params = {'query': '{id, name}'}
res = requests.get(
    USERS_URL,
    params=params,
    cookies=cookies  # Here we are sending cookies instead of `session_id`
)
# This will be small since we've retrieved only id and name
print(res.text)
```

</details>

#

## Allowed HTTP methods

#

## 1. POST

## Receive PRODUCTS From EKICLIK:

`POST /api/product.template/`

#### Headers

* Content-Type: application/json

#### Parameters

* NONE

### Request Body to insert a new product + configuration(s)

```js
{
    "params": {
        "data": {
            "name": "PRODUCT NAME",
            "brand": "BRAND NAME",
            "create_by": "ekiclic",
            "fab_name": "Fabriquant NAME",
            "categ_id": "CATEGORY NAME",
            "product_ref": "PRODUCT REFERENCE",
            "product": [
                {
                    "name": "CONFIGURATION NAME",
                    "description": "DESCRIPTION",
                    "default_code": null,
                    "detailed_type": "product",
                    "image_url": "IMAGE URL",
                    "list_price": 80000.0,
                    "standard_price": 50000.0,
                    "manufacturer_ref": "CONFIGURATION REFERENCE",
                    "purchase_ok": true,
                    "sale_ok": true,
                    "company_id": null,
                    "create_by": "ekiclic",
                    "attribute": [], <<< CHARACTERISTICS 
                    "fab_certificate": "CERTIFICATION URL"
                }
            ]
        }
    }
}
```

### Response

```js
{
    "jsonrpc": "2.0",
    "id": null,
    "result": 1
}
```

## Receive CLIENT / POS From EKICLIK:
`POST /api/res.partner/`

#### Headers

* Content-Type: application/json

#### Parameters

* NONE

### Request Body to insert a new client / POS
### 1- CLIENT

```js
{
    "params": {
        "data": {
            "create_by": "EkiClic",
            "is_company": false,
            "is_pos": "False",
            "status": "WAITING",
            "type": "contact",
            "title": null,
            "name": "CLIENT NAME",
            "email": "CLIENT ADDRESS",
            "phone": "0556000000",
        }
    }
}
```
### 2- POINT OF SALE
```js
{
    "params": {
        "data": {
            "create_by": "EkiClic",
            "is_company": false,
            "is_pos": "True",
            "status": "WAITING",
            "type": "contact",
            "title": null,
            "name": "POS NAME",
            "email": "POS ADDRESS",
            "phone": "0556000000",
            "code_pos": "PDVA-E-TIN-TIN-88-07",
            "credit_code": "CREDIT ANALYST CODE",
            "responsible_code": "RESPONSABLE CODE"
        }
    }
}
```

### Response

```js
{
    "jsonrpc": "2.0",
    "id": null,
    "result": 1
}
```
## Receive OPPORTUNITY (ORDER) from EKICLIK:
`POST /api/crm.lead/`

#### Headers

* Content-Type: application/json

#### Parameters

* NONE

### Request Body to insert a new opportunity

```js
{
    "params": {
        "data": {
            "create_by": "ekiclik",
            "order_source": "Alsalam",
            "partner": {
                "email": "CLIENT EMAIL",
                "salary": 900000.0,
                "birth_date": "1993-11-03",
                "monthly_payment": 5321,
                "periodicity": 12
            },
            "cart_id": 259,
            "cart": [
                {
                    "manufacturer_ref": "CONFIGURATION REFERENCE",
                    "quantity": 7,
                    "product_warehouse_id": "POS CODE"
                }
            ],
            "quotation_address": {
                "order_source": "Alsalam",
                "type": "delivery",
                "create_by": "ekiclick",
                "street": "POS ADDRESS",
                "street2": null,
                "state_id": "WILAYA",
                "country_id": "DZ",
                "code_pos": "POS CODE",
                "ek_order_id": 1416
            },
            "code_pos": "POS CODE",
            "file_info": {
                "file_number": 1906,
                "client_number": "0666666666",
                "order_status": "draft",
                "progress": 0.0,
                "file_state": "traitement"
            }
        }
    }
}
```

## Receive STOCK (PURCHASE) from EKICLIK:
`POST /api/purchase.order/`

#### Headers

* Content-Type: application/json

#### Parameters

* NONE

### Request Body to insert a new stock

```js
{
    "params": {
        "data": {
            "create_by": "ek",
            "partner_id": "PDVA-E-BOJ-BOJ-05-001",
            "user_id": 2,
            "state": "draft",
            "date_order": "30/07/23 12:23:15",
            "order_line": [
                {
                    "product_id": "CONFIGURATION REFERENCE",
                    "product_qty": 6,
                    "price_unit": 6000
                }
            ]
        }
    }
}

```
#  

## 2. PUT

## Update a Configuration From EKICLIK:

`PUT /api/product.template/`

#### Headers

* Content-Type: application/json

#### Parameters

* None

### Request Body

```js
{
    "params": {
        "filter": [["manufacturer_ref", "=", "CONFIGURATION REFERENCE"]],
        "data": {
            "create_by": "EKICLIK",
            "name": "UPDATED CONFIGURATION NAME",
        }
    }
}
```

### Response

```js
{
    "jsonrpc": "2.0",
    "id": null,
    "result": true
}
```

## Update a Product From EKICLIK:

`PUT /api/product.master/`

#### Headers

* Content-Type: application/json

#### Parameters

* None

### Request Body

```js
{
    "params": {
        "filter": [
            [
                "ref",
                "=",
                "PRODUCT REFERENCE"
            ]
        ],
        "data": {
            "name": "NAME",
            "brand": "UPDATED BRAND",
            "create_by": "ekiclic",
            "categ_id": "CATEGORY",
            "product_ref": "PRODUCT REFERENCE"
        }
    }
}
```

### Response

```js
{
    "jsonrpc": "2.0",
    "id": null,
    "result": true
}
```
## Update a order status From EKICLIK:

`PUT /api/sale.order/`

#### Headers

* Content-Type: application/json

#### Parameters

* None

### Request Body

```js
{
    "params": {
        "filter": [
            [
                "ek_order_id",
                "=",
                "1234"
            ]
        ],
        "data": {
            "create_by": "ekiclik",
            "order_source": "BNA",
            "state": "EK_ORDER_IN_PREPARATION"
        }
    }
}
```
## Update a Client/POS From EKICLIK:

`PUT /api/res.partner/`

#### Headers

* Content-Type: application/json

#### Parameters

* None

### Request Body

```js
{
    "params": {
        "filter": [
            [
                "email",
                "=",
                "CLIENT/POS ADDRESS"
            ]
        ],
        "data": {
            "create_by": "ekiclik",
            "name": "UPDATED NAME"
        }
    }
}
```

### Response

```js
{
    "jsonrpc": "2.0",
    "id": null,
    "result": true
}
```

## Update a User  From EKICLIK:

`PUT /api/res.users/`

#### Headers

* Content-Type: application/json

#### Parameters

* None

### Request Body

```js
{
    "params": {
        "filter": [
            [
                "login",
                "=",
                "user@mail.com"
            ]
        ],
        "data": {
            "name": "UPDATED NAME",
            "codification": "USER CODE",
            "email": "user@mail.com",
            "phone": "0667777777",
            "role": "ROLE_SUPERADMIN",
            "code_pos": "POS CODE",
            "create_by": "ekiclik"
        }
    }
}
```

### Response

```js
{
    "jsonrpc": "2.0",
    "id": null,
    "result": true
}
```


#
