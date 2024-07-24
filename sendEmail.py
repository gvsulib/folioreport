import smtplib
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from config import emailFrom
from email.mime.base import MIMEBase
from email import encoders
from sys import getsizeof

def hasItemsAboveMaxSize(attachmentArray, maxSize):
  isBigger = False
  for element in attachmentArray:
    if int(getsizeof(element)) > maxSize:
      isBigger = True
      break

  return isBigger

def splitAttachment(attachment):
  lines = attachment.split("\n")
  numberOfLines = len(lines)
  half = numberOfLines//2
  firstHalf = lines[:half]
  secondHalf = lines[half:]
  firstHalf = "\n".join(firstHalf)
  secondHalf = "\n".join(secondHalf)
  return [firstHalf,secondHalf]

def generateAttachmentArray(attachment, maxSize):
  attachmentArray = splitAttachment(attachment)
  while hasItemsAboveMaxSize(attachmentArray, maxSize):
    print(str(len(attachmentArray)))
    for index, value in enumerate(attachmentArray):
      itemSize = int(getsizeof(value))
      if itemSize > maxSize:
        attachmentArray.pop(index)
        attachmentArray.extend(splitAttachment(value))
  return attachmentArray


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
    session = smtplib.SMTP('smtp.gvsu.edu', 25)
    session.ehlo()
    maxLimit = int( session.esmtp_features['size'] )
    fileSize = int(getsizeof(attachment))
    if fileSize > maxLimit:
      bodyList = generateAttachmentArray(attachment, maxLimit)
      length = len(bodyList)
      current = 1
      for chunk in bodyList:
        newSubject = subject + " " + str(current) + " of " + str(length)
        print(newSubject)
        sendEmailWithAttachment(emailTo, fromAddr, newSubject, chunk)
        current += 1
      return

    part = MIMEBase('application', "octet-stream")
    part.set_payload(attachment)
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", "attachment; filename=%s" % filename)
    message.attach(part)
    text = message.as_string()
    session.sendmail(emailFrom, emailTo, text)
    session.quit()
  except Exception as e:
    msg = "Unable to send mail: " + str(e)
    subject = "Error: cannot email report"
    print(msg)
    sendEmail(emailTo, fromAddr, msg, subject)
    return
