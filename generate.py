import requests
import login
import sys
from flask import Flask
from config import okapiURL
from config import tenant
from config import mainURL
from config import emailFrom
from config import emailPass
import collections
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def getItemRecords(offset, okapiURL, itemPath, limitItem, location, headers):
  itemQueryString = '?limit=' + limitItem + '&offset=' + str(offset) + '&query=(effectiveLocationId=="' + location + '") sortby title'
  r = requests.get(okapiURL + itemPath + itemQueryString, headers=headers)
  if r.status_code != 200:
    print("Could not get item record data, status code: " + str(r.status_code) + " Error message:" + r.text)
    return -1
  else:
    return r.json()


token = login.login()

if token == 0:
  sys.exit()

logPath="/audit-data/circulation/logs"
itemPath = "/inventory/items"

endDate = "2021-10-22TT23:59:59.999"
startDate = "2021-08-01T00:00:00.000"

emailTo = "felkerk@gvsu.edu"

location = "0b64573b-b05f-4bad-aec9-f4e5fb98a637"

action = "Checked out"

limitLog = "100000"

limitItem = "100"

offset = 0

logQueryString = '?limit=' + limitLog + '&offset=0&query=((date>="'+ startDate +'" and date<="' + endDate + '") and action==("' + action + '")) sortby date/sort.descending'

headers = {'x-okapi-tenant': tenant, 'x-okapi-token': token}

print("attempting to get circ log data")

r = requests.get(okapiURL + logPath + logQueryString, headers=headers)

if r.status_code != 200:
  print("Could not get data from circulation log, status code: " + str(r.status_code) + " Error message:" + r.text)
  sys.exit()

temp = r.json()
logRecords = temp["logRecords"]
print(str(temp["totalRecords"]) + " records retrieved from circ log for given dates")

itemIdList = []
print("Counting circ log checkouts for the time period")
for entry in logRecords:
  itemIdList.append(entry["items"][0]["itemId"])

del logRecords

count = collections.Counter(itemIdList)

del itemIdList

print("Attempting to get item data from inventory")
itemResults = getItemRecords(offset, okapiURL, itemPath, limitItem, location, headers)

if itemResults == -1:
  sys.exit()

itemRecords = itemResults["items"]

totalRecords = itemResults["totalRecords"]

print(str(totalRecords) + " records in inventory for given location")

if totalRecords > 100:
  print("Location has more than 100 records, attempting to page through")
  offset = 100
  while offset < totalRecords:
    print("Attempting to fetch next 100 records from position " +str(offset))
    itemResults = getItemRecords(offset, okapiURL, itemPath, limitItem, location, headers)
    if itemResults == -1:
      sys.exit()
    itemRecords.extend(itemResults["items"])
    offset += 100
  print("All item records fetched!")
else:
  print("All Item records for location fetched")

print("Building csv file")
itemData = "Item id, Title, Barcode, Created Date, Location, Number of Checkouts\n"

for entry in itemRecords:
  x = []
  x.append(entry["id"])
  x.append('"' + entry["title"] + '"')
  if "barcode" in entry:
    x.append(entry["barcode"])
  else:
    x.append("")
  x.append(entry["metadata"]["createdDate"])
  x.append(entry["effectiveLocation"]["name"])

  if entry["id"] in count:
    x.append(str(count[entry["id"]]))
  else:
    x.append("0")

  itemData = itemData + ",".join(x) + "\n"

print("CSV data ready")

print("Attempting to Send Email report to " + emailTo)
try:
  emailBody = itemData.encode('utf-8')
  message = MIMEMultipart()
  message['From'] = emailFrom
  message['To'] = emailTo
  message['Subject'] = 'Checkout Report'   #The subject line
  message.attach(MIMEText(emailBody, 'csv'))
  #Create SMTP session for sending the mail
  session = smtplib.SMTP('smtp.gmail.com', 587) #use gmail with port
  session.starttls() #enable security
  session.login(emailFrom, emailPass) #login with mail_id and password
  text = message.as_string()
  session.sendmail(emailFrom, emailTo, text)
  session.quit()
except Exception as e:
  print("Unable to send mail: " + str(e))
print('Report sent')
print("Done, closing down")


  





















