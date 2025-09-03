import requests
import sys
import sendEmail
from errorHandler import errorHandler
from config import emailFrom
from config import techSupportEmail
from config import username
from config import password
from config import okapiURL
from config import tenant
from errorHandler import errorHandler

def login():
  handleError = errorHandler()
  handleError.setReportType("Folio API Login Error")
  path = "/authn/login-with-expiry"
  headers = {'x-okapi-tenant': tenant}
  payload={'username': username, 'password': password}
  
  r = requests.post(okapiURL + path, headers=headers, json=payload)

  if r.status_code != 201:
    handleError.handleErrorAndQuitNoUserEmail(handleError.constructHTTPErrorMessage(okapiURL, r))

  return r.cookies["folioAccessToken"]

def getNewHeaders():
  token = login()
  return {'x-okapi-tenant': tenant, 'x-okapi-token': token}



