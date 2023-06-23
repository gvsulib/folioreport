from flask import Flask, render_template, redirect, request
from flask.helpers import make_response
from config import secretKey, okapiURL, tenant, externalPass
import login
import requests
import sys
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms.fields.html5 import DateField, EmailField
from wtforms import SubmitField, SelectMultipleField, PasswordField, BooleanField, TextField
from wtforms.validators import InputRequired, Email
from threading import Thread
from generate import generateTemporaryLoanItem
from generate import generateReport
from generate import generateReservesUse
from generate import generateInventoryReport
from flask_wtf.csrf import CSRFProtect
from datetime import datetime

now = datetime.now()
today = now.date()
formDate = str(today.day) + "/" + str(today.month) + "/" + str(today.year)

# Flask-WTF requires an encryption key - the string can be anything
app = Flask(__name__)
csrf = CSRFProtect(app)
token = login.login()
if token == 0:
  sys.exit()
error = ""
locationPath = "/locations?limit=2000&query=cql.allRecords%3D1%20sortby%20name"
headers = {'x-okapi-tenant': tenant, 'x-okapi-token': token}
#selectmultipleField will auto-fail validation and refuse to submit form
#without this
class NoValidationSelectMultipleField(SelectMultipleField):
    def pre_validate(self, form):
      pass
      """per_validation is disabled"""

r = requests.get(okapiURL + locationPath, headers=headers)
if r.status_code != 200:
  error = "Cannot Get location code data from folio: " + str(r.status_code) + r.text
  sys.exit()

temp = r.json()
locations = temp["locations"]
if len(locations) == 0:
  error = "No locations defined."

selectValues = []
for entry in locations:
  selectValues.append(([entry["id"]], entry["name"]))


Bootstrap(app)
app.config['SECRET_KEY'] = secretKey

class temporaryLoanItemReportForm(FlaskForm):
  email = EmailField('Email the report to: ', validators=[InputRequired(), Email()])
  submit = SubmitField('Submit')

class authenticationForm(FlaskForm):
  password = PasswordField('Enter Password: ', validators=[InputRequired()])
  submit = SubmitField('Submit')

class InventoryForm(FlaskForm):

  email = EmailField('Email the report to: ', validators=[InputRequired(), Email()])
  location = NoValidationSelectMultipleField('Location:', choices=selectValues, validators=[InputRequired()])
  callNumberStem = TextField('Call Number Stem')
  cutoffDate = DateField('Cut Off Date:', validators=[InputRequired()], format='%Y-%m-%d')
  submit = SubmitField('Submit')

d = datetime(2021, 7, 1)

class UseReportForm(FlaskForm):

  email = EmailField('Email the report to: ', validators=[InputRequired(), Email()])
  location = NoValidationSelectMultipleField('Location:', choices=selectValues)
  callNumberStem = TextField('Call Number Stem')
  startDate = DateField('Start Date:', default=d, validators=[InputRequired()], format='%Y-%m-%d')
  endDate = DateField('End Date:', default=datetime.today, validators=[InputRequired()],  format='%Y-%m-%d')
  includeSuppressed = BooleanField('Include suppressed records')
  submit = SubmitField('Submit')

class  ReservesReportForm(FlaskForm):
  email = EmailField('Email the report to: ', validators=[InputRequired(), Email()])
  submit = SubmitField('Generate Reserves Usage Report')

class temporaryLoanItemThread (Thread):
  def __init__(self, emailAddr, locations):
    Thread.__init__(self)
    self.emailAddr = emailAddr
    self.locations = locations
  def run (self):
    print("Starting temporary loan item report")
    generateTemporaryLoanItem(self.emailAddr, locations)
    print("Finished, Shutting Down")

class reservesThread (Thread):
  def __init__(self, emailAddr):
      Thread.__init__(self)
      self.emailAddr = emailAddr
  def run (self):
    print("Starting reserves report")
    generateReservesUse(self.emailAddr)
    print("Finished, Shutting Down")

class inventoryThread (Thread):
   def __init__(self, cutoffDate, locationId, emailAddr, callNumberStem):
      Thread.__init__(self)
      self.cutoffDate = cutoffDate
      self.locationId = locationId
      self.emailAddr = emailAddr
      self.callNumberStem = callNumberStem
   def run(self):
      print("Starting inventory report")
      generateInventoryReport(self.cutoffDate, self.locationId, self.emailAddr, self.callNumberStem)
      print("finished, shutting down")

class myThread (Thread):
   def __init__(self, startDate, endDate, locationId, emailAddr, includeSuppressed, callNumberStem):
      Thread.__init__(self)
      self.startDate = startDate
      self.endDate = endDate
      self.locationId = locationId
      self.emailAddr = emailAddr
      self.includeSuppressed = includeSuppressed
      self.callNumberStem = callNumberStem
   def run(self):
      print("Starting report")
      generateReport(self.startDate, self.endDate, self.locationId, self.emailAddr, self.includeSuppressed, self.callNumberStem)
      print("finished, shutting down")

@app.route('/login', methods=['GET', 'POST'])
def login():
  formName = "Login"
  authForm = authenticationForm()
  loggedIn = request.cookies.get('loggedIn')
  if loggedIn != None and loggedIn == "true":
    return redirect("/reports/choose", code=302)
  if authForm.validate_on_submit():
    passwd = authForm.password.data
    if passwd != externalPass.strip():
      message = "Invalid Password"
      return render_template('index.html', form=authForm, message=message,formName=formName)
    else:
      resp = make_response(redirect("/reports/choose", code=302))
      resp.set_cookie('loggedIn', 'true')
      return resp
  return render_template('index.html', form=authForm, message="", formName=formName)

@app.route('/temploanitem', methods=['GET', 'POST'])
def temporaryLoanItem():
  formName = "Items on temporary loan report"
  loggedIn = request.cookies.get('loggedIn')
  if loggedIn == None or loggedIn != "true":
    return redirect("/reports/login", code=302)
  tempLoanItemForm = temporaryLoanItemReportForm()
  if tempLoanItemForm.validate_on_submit():
    email = tempLoanItemForm.email.data
    thread1 = temporaryLoanItemThread(email, locations)
    thread1.start()
    return render_template('success.html')
  return render_template('index.html', form=tempLoanItemForm, message="", formName=formName)

@app.route('/reservereport', methods=['GET', 'POST'])
def reservereport():
  formName = "Reserves use report"
  loggedIn = request.cookies.get('loggedIn')
  if loggedIn == None or loggedIn != "true":
    return redirect("/reports/login", code=302)
  reservesReportForm = ReservesReportForm()
  if reservesReportForm.validate_on_submit():
    email = reservesReportForm.email.data
    thread1 = reservesThread(email)
    thread1.start()
    return render_template('success.html')
  return render_template('index.html', form=reservesReportForm, message="", formName=formName)
  
@app.route('/choose', methods=['GET'])
def choose():
  loggedIn = request.cookies.get('loggedIn')
  if loggedIn == None or loggedIn != "true":
    return redirect("/reports/login", code=302)
  return render_template('choose.html')

@app.route('/inventoryreport', methods=['GET', 'POST'])
def inventoryreport():
  inventoryReportForm = InventoryForm()
  formName = 'Inventory Report Form'
  message = ""

  if error != "":
    return render_template('error.html', message=error)

  if inventoryReportForm.validate_on_submit():
    cutoffDate = inventoryReportForm.cutoffDate.data
    email = inventoryReportForm.email.data
    location = inventoryReportForm.location.data
    callNumberStem = inventoryReportForm.callNumberStem.data
    cutoffDate = cutoffDate.strftime('%Y-%m-%d')
    thread1 = inventoryThread(cutoffDate, location, email, callNumberStem)
    thread1.start()
    
    return render_template('success.html')
  return render_template('index.html', form=inventoryReportForm, message=message, formName=formName)

@app.route('/usereport', methods=['GET', 'POST'])
def usereport():

  useReportForm = UseReportForm()
  formName = "Checkout Report Form"
  message = ""
  
  if error != "":
    return render_template('error.html', message=error)

  if useReportForm.validate_on_submit():
    endDate = useReportForm.endDate.data
    startDate = useReportForm.startDate.data 
    email = useReportForm.email.data
    location = useReportForm.location.data
    includeSuppressed = useReportForm.includeSuppressed.data
    callNumberStem = useReportForm.callNumberStem.data

    if endDate < startDate:
      message = "End date cannot be before start date." 
      return render_template('index.html', form=useReportForm, message=message)
    elif callNumberStem == "" and len(location) == 0:
      message = "You must select one or more locations, input a call number stem, or both"
      return render_template('index.html', form=useReportForm, message=message, formName=formName)
    else:
      startDate = startDate.strftime('%Y-%m-%d')
      endDate = endDate.strftime('%Y-%m-%d')
      thread1 = myThread(startDate, endDate, location, email, includeSuppressed, callNumberStem)
      thread1.start()
      return render_template('success.html')
  return render_template('index.html', form=useReportForm, message=message, formName=formName)


