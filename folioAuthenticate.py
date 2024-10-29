import requests
import sys
import sendEmail
from config import emailFrom

from config import username
from config import password
from config import okapiURL
from config import tenant

emailTo = "felkerk@gvsu.edu"

def handleErrorAndQuit(msg, emailTo):
  sendEmail.sendEmail(emailTo, emailFrom, msg, "Error Generating reports")
  sys.exit()

def login():
  path = "/authn/login-with-expiry"
  headers = {'x-okapi-tenant': tenant}
  payload={'username': username, 'password': password}
  
  r = requests.post(okapiURL + path, headers=headers, json=payload)

  if r.status_code != 201:
    msg = "Login to folio failed, status code: " + str(r.status_code) + " Error message: " + r.text
    handleErrorAndQuit(msg, emailTo)

  return r.cookies["folioAccessToken"]

def getNewHeaders():
  token = login()
  return {'x-okapi-tenant': tenant, 'x-okapi-token': token}



