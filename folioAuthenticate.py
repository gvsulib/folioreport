import requests

from config import username
from config import password
from config import okapiURL
from config import tenant

def login():
  path = "/authn/login-with-expiry"
  headers = {'x-okapi-tenant': tenant}
  payload={'username': username, 'password': password}
  
  r = requests.post(okapiURL + path, headers=headers, json=payload)

  if r.status_code != 201:
    print("Login failed, status code: " + str(r.status_code) + " Error message: " + r.text)
    return 0

  return r.cookies["folioAccessToken"]

def logout(token):
  path = "/authn/logout"
  headers = {'x-okapi-tenant': tenant, 'x-okapi-token': token}
  payload={}
  
  r = requests.post(okapiURL + path, headers=headers, json=payload)

