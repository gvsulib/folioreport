import requests

from config import username
from config import password
from config import okapiURL
from config import tenant

def login():
  print("Attempting to log in...")

  path = "/bl-users/login"
  headers = {'x-okapi-tenant': tenant}
  payload={'username': username, 'password': password}
  parameters = {"expandPermissions":"true", "fullPermissions": "true"}

  r = requests.post(okapiURL + path, params=parameters, headers=headers, json=payload)

  if r.status_code == 201:
    print("Login successful!")
  else:
    print("Login failed, status code: " + str(r.status_code) + " Error message: " + r.text)
    return 0

  return r.headers.get("x-okapi-token")



