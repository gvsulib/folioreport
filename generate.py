import requests
import login
import sys
import sendEmail
from config import okapiURL
from config import tenant
from config import emailFrom
import collections

def getItemRecords(email, offset, okapiURL, itemPath, limitItem, locationList, headers):
  locationQuery = 'effectiveLocationId==('
  
  for index, location in enumerate(locationList):
    if index == 0:
      locationQuery = 'effectiveLocationId==("' + location + '"'
    else:
      locationQuery = locationQuery + ' or "' + location + '"'
  itemQueryString = '?limit=' + limitItem + '&offset=' + str(offset) + '&query=' + locationQuery + ') sortby title'
  
  r = requests.get(okapiURL + itemPath + itemQueryString, headers=headers)
  if r.status_code != 200:
    error = "Could not get item record data, status code: " + str(r.status_code) + " Error message:" + r.text
    print(error)
    sendEmail.sendEmail(email, emailFrom, error, "Error Generating checkout report")
    return -1
  else:
    return r.json()

def generateReport(startDate, endDate, locationList, emailAddr): 
  disallowed_characters = "''[]"

  for index, location in enumerate(locationList):
    for character in disallowed_characters:
	    location = location.replace(character, "")
    locationList[index] = location
    

  print("locations" + str(locationList))
  token = login.login()
  if token == 0:
      error = "Unable to log in to folio."
      print(error)
      sendEmail.sendEmail(emailAddr, emailFrom, error, "Error Generating checkout report")
      sys.exit()
    
  logPath="/audit-data/circulation/logs"
  itemPath = "/inventory/items"

  limitLog = "100000"

  limitItem = "100"

  offset = 0
  
  logQueryString = "?limit=" + limitLog + "&offset=0&query=%28%28date%3E%3D%22" + startDate + "T00%3A00%3A00.000%22%20and%20date%3C%3D%22" + endDate + "T23%3A59%3A59.999%22%29%20and%20action%3D%3D%28%22Checked%20out%22%29%29%20sortby%20date%2Fsort.descending"

  headers = {'x-okapi-tenant': tenant, 'x-okapi-token': token}

  print("attempting to get circ log data")
  
  r = requests.get(okapiURL + logPath + logQueryString, headers=headers)

  if r.status_code != 200:
    error = "Could not get data from circulation log, status code: " + str(r.status_code) + " Error message:" + r.text
    print(error)
    sendEmail.sendEmail(emailAddr, emailFrom, error, "Error Generating checkout report")
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

  itemResults = getItemRecords(emailAddr, offset, okapiURL, itemPath, limitItem, locationList, headers)

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
      itemResults = getItemRecords(emailAddr, offset, okapiURL, itemPath, limitItem, locationList, headers)
      if itemResults == -1:
        sys.exit()
      itemRecords.extend(itemResults["items"])
      offset += 100
    print("All item records fetched!")
  else:
    print("All Item records for location fetched")

  print("Building csv file")
  itemData = "Item id, Location, Call Number, Title, Barcode, Created Date, Number of Checkouts\n"

  for entry in itemRecords:
    x = []
    x.append(entry["id"])
    x.append('"' + entry["effectiveLocation"]["name"] + '"')
    if "barcode" in entry:
      x.append('"' + entry["callNumber"] + '"')
    else:
      x.append("")
    x.append('"' + entry["title"] + '"')
    if "barcode" in entry:
      x.append(entry["barcode"])
    else:
      x.append("")
    x.append(entry["metadata"]["createdDate"])
    if entry["id"] in count:
      x.append(str(count[entry["id"]]))
    else:
      x.append("0")

    itemData = itemData + ",".join(x) + "\n"

  print("CSV data ready")

  sendEmail.sendEmailWithAttachment(emailAddr, emailFrom, "Checkout Report", itemData)
  print('Report sent')
  print("Done, closing down")


  





















