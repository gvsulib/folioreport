import smtplib
from email.message import EmailMessage
from config import techSupportEmail, emailFrom
import sys

class errorHandler:
  def __init__(self):
    self.techSupportEmail = techSupportEmail
    self.userEmail = None
    self.emailFrom = emailFrom
    self.reportType = None
    self.params = None
  
  def setUserEmail(self, email):
    self.userEmail = email

  def setParams(self, params):
    self.params = params

  def setReportType(self, type):
    self.reportType = type

  def constructHTTPErrorMessage(url, response):
    return "Could not get data from endpoint:" +  url + "\n status code: " + str(response.status_code) + "\n Error message:" + response.text

  def sendEmail(self, subject, content, emailTo):
  
    message = EmailMessage()
    message.set_content(content)
    message['From'] = self.emailFrom
    message['To'] = emailTo
    message['Subject'] = subject
  
    try:
      session = smtplib.SMTP('smtp.gvsu.edu', 25) #use gmail with port
      session.send_message(message)
      session.quit()
    except Exception as e:
      print("Unable to send mail: " + str(e))
      sys.exit()
    return
  
  def composeMessageBody(self, errorMessage):
    body = "Error running report " + self.reportType + "\n\n"
    body += "Error message: " + errorMessage + "\n"

    if self.params is not None:
      body += "Report Parameters: \n\n"
      for key, value in self.params.items():
        body += key + ":" + value + "\n"

    return body

  def handleErrorAndQuitNoTechEmail(self, errorMsg):
    mailBody = self.composeMessageBody(errorMsg)
    subject = "Error running folio report"
    self.sendEmail(subject, mailBody, self.userEmail)
    sys.exit()

  def handleErrorAndQuitNoUserEmail(self, errorMsg):
    mailBody = self.composeMessageBody(errorMsg)
    subject = "Error running folio report"
    self.sendEmail(subject, mailBody, self.techSupportEmail)
    sys.exit()

  def handleErrorAndQuit(self, errorMsg):
    mailBody = self.composeMessageBody(errorMsg)
    subject = "Error running folio report"
    self.sendEmail(subject, mailBody, self.techSupportEmail)
    mailBody += "A copy of this email has been sent to the tech support person."
    self.sendEmail(subject, mailBody, self.userEmail)
    sys.exit()


  