import smtplib
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config import emailFrom
from email.mime.base import MIMEBase
from email import encoders

def sendEmail(emailTo, fromAddr, messageBody, subject):
  
  message = EmailMessage()
  message.set_content(messageBody)
  message['From'] = fromAddr
  message['To'] = emailTo
  message['Subject'] = subject
  
  try:
    session = smtplib.SMTP('smtp.gvsu.edu', 25) #use gmail with port
    session.send_message(message)
    session.quit()
  except Exception as e:
    print("Unable to send mail: " + str(e))
    return


def sendEmailWithAttachment(emailTo, fromAddr, subject, attachment):
  print("Attempting to Send Email report to " + emailTo)
  filename = "report.csv"
  try:
    message = MIMEMultipart()
    message['From'] = fromAddr
    message['To'] = emailTo
    message['Subject'] = subject   #The subject line

    part = MIMEBase('application', "octet-stream")
    part.set_payload(attachment)
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", "attachment; filename=%s" % filename)
    message.attach(part)
    #Create SMTP session for sending the mail
    session = smtplib.SMTP('smtp.gvsu.edu', 25) #use gmail with port
    text = message.as_string()
    session.sendmail(emailFrom, emailTo, text)
    session.quit()
  except Exception as e:
    print("Unable to send mail: " + str(e))
    return
