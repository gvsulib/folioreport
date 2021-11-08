from flask import Flask, render_template, redirect, request
from flask.helpers import make_response
from config import secretKey, okapiURL, tenant, externalPass
import login
import requests
from flask_bootstrap import Bootstrap
from flask_wtf import FlaskForm
from wtforms.fields.html5 import DateField, EmailField
from wtforms import SubmitField, SelectField, PasswordField
from wtforms.validators import DataRequired, Email
from threading import Thread
from generate import generateReport
# Flask-WTF requires an encryption key - the string can be anything
app = Flask(__name__)
token = login.login()
error = ""
locationPath = "/locations?limit=2000&query=cql.allRecords%3D1%20sortby%20name"
headers = {'x-okapi-tenant': tenant, 'x-okapi-token': token}

r = requests.get(okapiURL + locationPath, headers=headers)
if r.status_code != 200:
  error = "Cannot Get location code data from folio: " + str(r.status_code) + r.text

temp = r.json()
locations = temp["locations"]
if len(locations) == 0:
  error = "No locations defined."

selectValues = []
for entry in locations:
  selectValues.append(([entry["id"]], entry["name"]))


Bootstrap(app)
app.config['SECRET_KEY'] = secretKey

class authenticationForm(FlaskForm):
  password = PasswordField('Enter Password: ', validators=[DataRequired()])
  submit = SubmitField('Submit')

class ReportForm(FlaskForm):

  email = EmailField('Email the report to: ', validators=[DataRequired(), Email()])
  location = SelectField('Location:', choices=selectValues, validators=[DataRequired()])
  startDate = DateField('Start Date:', validators=[DataRequired()], format='%Y-%m-%d')
  endDate = DateField('End Date:', validators=[DataRequired()],  format='%Y-%m-%d')
  submit = SubmitField('Submit')

class myThread (Thread):
   def __init__(self, startDate, endDate, locationId, emailAddr):
      Thread.__init__(self)
      self.startDate = startDate
      self.endDate = endDate
      self.locationId = locationId
      self.emailAddr = emailAddr
   def run(self):
      print("Starting report")
      generateReport(self.startDate, self.endDate, self.locationId, self.emailAddr)
      print("finished, shutting down")

@app.route('/login', methods=['GET', 'POST'])
def login():
  authForm = authenticationForm()
  loggedIn = request.cookies.get('loggedIn')
  if loggedIn != None and loggedIn == "true":
    return redirect("/report", code=302)
  if authForm.validate_on_submit():
    passwd = authForm.password.data
    if passwd != externalPass.strip():
      message = "Invalid Password"
      return render_template('index.html', form=authForm, message=message)
    else:
      resp = make_response(redirect("/report", code=302))
      resp.set_cookie('loggedIn', 'true')
      return resp
  return render_template('index.html', form=authForm, message="")

@app.route('/report', methods=['GET', 'POST'])
def report():
  loggedIn = request.cookies.get('loggedIn')
  if loggedIn == None or loggedIn != "true":
    return redirect("/login", code=302)
  reportForm = ReportForm()
  message = ""
  
  if error != "":
    return render_template('error.html', message=error)

  if reportForm.validate_on_submit():
    
    endDate = reportForm.endDate.data
    startDate = reportForm.startDate.data 
    email = reportForm.email.data
    location = reportForm.location.data
    if endDate < startDate:
      message = "End date cannot be before start date." 
      return render_template('index.html', form=reportForm, message=message)
    else:
      startDate = startDate.strftime('%Y-%m-%d')
      endDate = endDate.strftime('%Y-%m-%d')
      thread1 = myThread(startDate, endDate, location, email)
      thread1.start()
      return render_template('success.html')
  return render_template('index.html', form=reportForm, message=message)


