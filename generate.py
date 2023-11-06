import requests
import login
import sys
import sendEmail
from config import okapiURL
from config import tenant
from config import emailFrom
import collections
from requests.adapters import HTTPAdapter, Retry

logPath="/audit-data/circulation/logs"

emailTo = "felkerk@gvsu.edu"

def handleErrorAndQuit(msg, emailTo, reportType):
    print(msg)
    sendEmail.sendEmail(emailTo, emailFrom, msg, "Error Generating" + reportType + "Report")
    sys.exit()

def getTitleforItem(itemid, headers, session):
  url = okapiURL + "/inventory/items/" + itemid
  r = session.get(url, headers=headers)
  print("Attempting to get title data from: " + url)
  if r.status_code != 200:
    error = "Could not get data from endpoint, status code: " + str(r.status_code) + " Error message:" + r.text
    print(error)
    sendEmail.sendEmail(emailTo, emailFrom, error, "Error Generating checkout report")
    sys.exit()
  return r.json()["title"]

def getRecordById(id, path, headers, session):
  url = okapiURL + path + id
  print("Attempting to get record from: " + url + " with id: " + str(id))
  r = session.get(url, headers=headers)
  if r.status_code != 200:
    error = "Could not get data from endpoint, status code: " + str(r.status_code) + " Error message:" + r.text
    print(error)
    sendEmail.sendEmail(emailTo, emailFrom, error, "Error Generating checkout report")
    sys.exit()
  return r.json()

def getRetentionDataFromHoldings(itemRecord, headers, session):
  holdingsId = itemRecord["holdingsRecordId"]
  path = "/holdings-storage/holdings/"
  json = getRecordById(holdingsId, path, headers, session)
  if "retentionPolicy" in json:
    return "\"" + json["retentionPolicy"] + "\""
  else:
    return ""

def getLocationsFromHoldings(holdingsId, headers, session):
  url = okapiURL + "/holdings-storage/holdings/" + holdingsId
  print(url)
  print("Attempting to get holdings data from: " + url)
  r = session.get(url, headers=headers)
  if r.status_code != 200:
    error = "Could not get data from endpoint, status code: " + str(r.status_code) + " Error message:" + r.text
    print(error)
    sendEmail.sendEmail(emailTo, emailFrom, error, "Error Generating checkout report")
    sys.exit()
  json = r.json()
  locations = {}
  locations["Permanent"] = json["permanentLocationId"]
  locations["Effective"] = json["effectiveLocationId"]
  if "temporaryLocationId" in json:
    locations["Temporary"] = json["temporaryLocationId"]
  return locations
  
def getAllFromEndPoint(path, queryString, arrayName, headers, session):
  limit = "100"
  offset = 0

  fullQuery = "?limit=" + limit + "&offset=" + str(offset) + queryString

  print(str(fullQuery))

  r = session.get(okapiURL + path + fullQuery, headers=headers)
  print("Attempting to get data from endpoint: " + path)
  if r.status_code != 200:
    error = "Could not get data from endpoint, status code: " + str(r.status_code) + " Error message:" + r.text
    print(error)
    sendEmail.sendEmail(emailTo, emailFrom, error, "Error Generating checkout report")
    sys.exit()
  json = r.json()[arrayName]

  if len(json) < 1:
    return []
  
  list = json

  while json:
    offset += 100
    fullQuery = "?limit=" + limit + "&offset=" + str(offset) + queryString
    print("attempting to fetch next 100 entries from " + str(offset))
    r = session.get(okapiURL + path + fullQuery, headers=headers)
    json = r.json()[arrayName]
    if len(json) >= 1:
      list = list + json
    else:
      print("No more data to fetch")
  return list

def generateReservesUse(emailAddr):
  reportType = "Reserves Use"
  session = requests.Session()

  retries = Retry(total=5, backoff_factor=0.1)
  session.mount('https://', HTTPAdapter(max_retries=retries))
  emailTo = emailAddr
  
  token = login.login()
  if token == 0:
    error = "Unable to log in to folio."
    handleErrorAndQuit(error, emailTo, reportType)

  reservesPath = "/coursereserves/reserves"
  arrayName = "reserves"
  query = ""
  headers = {'x-okapi-tenant': tenant, 'x-okapi-token': token}
  print("Attempting to get course and instructor data")
  result = getAllFromEndPoint("/coursereserves/courses", "", "courses", headers, session)
  if len(result) < 1:
    msg = "No reserves data found in reserves endpoint"
    handleErrorAndQuit(error, emailTo, reportType)
  print("instructor and course data retrieved")
  #extract course names from courses data
  courses = []
  for entry in result:
    name = ""
    if len(entry["courseListingObject"]["instructorObjects"]) != 0:
      name = entry["courseListingObject"]["instructorObjects"][0]["name"]

    courses.append({
      "courseName": entry["name"], 
      "courseCode":entry["courseNumber"],
      "instructor": name,
      "courseListingId":entry["courseListingId"]
      })
  print("Getting location data")
  result = getAllFromEndPoint("/locations", "", "locations", headers, session)
  print("Location data retrieved")

  #format location data to list with id number as key
  locations = {}
  for entry in result:
    locations.update({entry["id"]: entry["name"]})

  #get start and end dates from reserves data
  print("Getting listing of reserve items")
  result = getAllFromEndPoint("/coursereserves/reserves", "", "reserves", headers, session)

  #combine course and item data into single entries
  reserveItems = []
  for entry in result:
    print("entry" + str(entry))
    location = ""
    if "temporaryLocationId" in entry["copiedItem"]:
      location = entry["copiedItem"]["temporaryLocationId"]
    elif "permanentLocationId" in entry["copiedItem"]:
      location = entry["copiedItem"]["permanentLocationId"]
    barcode = ""
    if "barcode" in entry["copiedItem"]:
      barcode = entry["copiedItem"]["barcode"]

    locationText = locations[location]

    itemEntry = {
      "id": entry["itemId"],
      "title":entry["copiedItem"]["title"],
      "barcode":barcode,
      "location": locationText,
      }
    for course in courses:
      if course["courseListingId"] == entry["courseListingId"]:
        itemEntry.update(course)
        del itemEntry["courseListingId"]
        break

    reserveItems.append(itemEntry)

  print("Reserve items retrieved")
  
  print("extracting start and end dates")
  startDate = result[0]["startDate"]

  print("start date: " + startDate)

  endDate = result[0]["endDate"]

  print("end date: " + endDate)

  print("Attempting to get data from circ logs for the time period: " + startDate + " to " + endDate)

  logQueryString = "&query=%28%28date%3E%3D%22" + startDate + "T00%3A00%3A00.000%22%20and%20date%3C%3D%22" + endDate + "T23%3A59%3A59.999%22%29%20and%20action%3D%3D%28%22Checked%20out*%22%29%29%20sortby%20date%2Fsort.descending"

  #get circ log data for date ranges
  result = getAllFromEndPoint(logPath, logQueryString, "logRecords", headers, session)
  if len(result) < 1:
    error="No circulation data found for date ranges provided"
    handleErrorAndQuit(error, emailTo, reportType)
  print("Data from circ logs retrieved")
  itemIdList = []
  print("Counting circ log checkouts for the time period: " + startDate + " to " + endDate)
  for entry in result:
    itemIdList.append(entry["items"][0]["itemId"])
  count = collections.Counter(itemIdList)
  print("collating data for final report to CSV")
  itemData = "Item id, title, Barcode, location, course name, course code, instructor, folio checkout events\n"

  for item in reserveItems:
    x = []
    x.append(item["id"])
    x.append("\"" + item["title"] + "\"")
    x.append("\"" + item["barcode"] + "\"")
    x.append("\"" + item["location"] + "\"")
    x.append("\"" + item["courseName"] + "\"")
    x.append("\"" + item["courseCode"] + "\"")
    x.append("\"" + item["instructor"] + "\"")
    if item["id"] in count:
      x.append(str(count[item["id"]]))
    else:
      x.append("0")
    itemData = itemData + ",".join(x) + "\n"

  print("CSV data ready")
  sendEmail.sendEmailWithAttachment(emailAddr, emailFrom, "Checkout Report", itemData)
  print('Reserves Report sent')
  print("Done, closing down")

def constructLocationQuery(locationList):
  if len(locationList) == 0:
    return 'effectiveLocationId==("*")'
  else:
    locationQuery = ""
  
    for index, location in enumerate(locationList):
      if index == 0:
        locationQuery = 'effectiveLocationId==("' + location + '"'
      else:
        locationQuery = locationQuery + ' or "' + location + '"'
    
    return locationQuery + ')'


def getItemRecords(email, offset, okapiURL, itemPath, limitItem, locationList, headers, callNumberStem, addStatus, cutoffDate, session):
  locationQuery = constructLocationQuery(locationList)
  cutoffQuery = ''
  statusQuery = ''
  callNumberQuery = ''
  if addStatus:
    statusQuery = ' and (status.name==("Available") or status.name==("in transit"))'

  if cutoffDate is not None:
    cutoffQuery = ' and lastCheckIn.dateTime<=("' + cutoffDate + 'T00:00:00.000")'
  
  if callNumberStem != "":
    callNumberQuery = ' and effectiveCallNumberComponents.callNumber==("' + callNumberStem + '*")'
  itemQueryString = '?limit=' + limitItem + '&offset=' + str(offset) + '&query=(' + locationQuery + callNumberQuery + cutoffQuery + statusQuery + ') sortby title'
  #print("item query: " + itemQueryString)
  r = session.get(okapiURL + itemPath + itemQueryString, headers=headers)
  if r.status_code != 200:
    error = "Could not get item record data, status code: " + str(r.status_code) + " Error message:" + r.text
    print(error)
    sendEmail.sendEmail(email, emailFrom, error, "Error Generating checkout report")
    return -1
  else:
    json = r.json()
    return json["items"]

def generateInventoryEntry(entry):
  x = []
  x.append(entry["id"])
  x.append('"' + entry["effectiveLocation"]["name"] + '"')
  if "callNumber" in entry:
    x.append('"' + entry["callNumber"] + '"')
  else:
    x.append("")
  x.append('"' + entry["title"] + '"')
  if "barcode" in entry:
    x.append(entry["barcode"])
  else:
    x.append("")
  x.append(entry["status"]["name"])
  if "lastCheckIn" in entry:
    if "dateTime" in entry["lastCheckIn"]:
      x.append('"' + entry["lastCheckIn"]["dateTime"] + '"')
  else:
    x.append("")
  return ",".join(x) + "\n"


def generateCheckoutEntry(entry, count, retentionData):
  totalCheckout = "none"
  x = []
  x.append(entry["id"])
  x.append('"' + entry["effectiveLocation"]["name"] + '"')
  if "callNumber" in entry:
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
  if "notes" in entry:
    notes = entry["notes"]
    for note in notes:
      if note["itemNoteTypeId"] == "6d8bb43a-7455-4044-836e-f43740a4c38d":
        totalCheckout = note["note"]

  x.append(totalCheckout)
  x.append(retentionData)
  return ",".join(x) + "\n"


def generateInventoryReport(cutoffDate, locationList, emailAddr, callNumberStem):
  reportType="item use report"
  session = requests.Session()

  retries = Retry(total=5, backoff_factor=0.1)
  session.mount('https://', HTTPAdapter(max_retries=retries))
  disallowed_characters = "''[]"

  for index, location in enumerate(locationList):
    for character in disallowed_characters:
      location = location.replace(character, "")
    locationList[index] = location

  token = login.login()
  if token == 0:
    error = "Unable to log in to folio."
    handleErrorAndQuit(error, emailTo, reportType)

  itemPath = "/inventory/items"

  limit = "100"

  offset = 0

  headers = {'x-okapi-tenant': tenant, 'x-okapi-token': token}

  print("attempting to get inventory item data")

  itemResults = getItemRecords(emailAddr, offset, okapiURL, itemPath, limit, locationList, headers, callNumberStem, True, cutoffDate, session)
  
  if itemResults == -1:
    error="Cannot find any item data that matches criteria provided"
    handleErrorAndQuit(error, emailTo, reportType)

  itemData = "Item id, Location, Call Number, Title, Barcode, Status, Status Update Date\n"
  itemIds = []
  while itemResults:
    for item in itemResults:
      if item["id"] not in itemIds:
        itemIds.append(item["id"])
        if (("discoverySuppress" not in item) or (item["discoverySuppress"] != True)):
          print("logging data for item " + item["id"])
          itemData = itemData + generateInventoryEntry(item)
    offset += 100
    print("Attempting to get next 100 records from offset " + str(offset))
    itemResults = getItemRecords(emailAddr, offset, okapiURL, itemPath, limit, locationList, headers, callNumberStem, True, cutoffDate, session)
  
  print("CSV data ready")

  sendEmail.sendEmailWithAttachment(emailAddr, emailFrom, "Inventory Report", itemData)
  print('Report sent')
  print("Done, closing down")


def generateCheckoutReport(startDate, endDate, locationList, emailAddr, includeSuppressed, callNumberStem): 
  reportType="Item use report"
  session = requests.Session()

  retries = Retry(total=5, backoff_factor=0.1)
  session.mount('https://', HTTPAdapter(max_retries=retries))
  disallowed_characters = "''[]"

  for index, location in enumerate(locationList):
    for character in disallowed_characters:
      location = location.replace(character, "")
    locationList[index] = location

  token = login.login()
  if token == 0:
    error = "Cannot log into folio"
    handleErrorAndQuit(error, emailTo, reportType)

  itemPath = "/inventory/items"

  limitLog = "100000"

  limitItem = "99"

  offset = 0
  
  logQueryString = "?limit=" + limitLog + "&offset=0&query=%28%28date%3E%3D%22" + startDate + "T00%3A00%3A00.000%22%20and%20date%3C%3D%22" + endDate + "T23%3A59%3A59.999%22%29%20and%20action%3D%3D%28%22Checked%20out*%22%29%29%20sortby%20date%2Fsort.descending"
  
  headers = {'x-okapi-tenant': tenant, 'x-okapi-token': token}

  print("attempting to get circ log data")
  print(" circ log url: " + okapiURL + logPath + logQueryString)
  r = session.get(okapiURL + logPath + logQueryString, headers=headers)

  if r.status_code != 200:
    error = "Could not get data from circulation log, status code: " + str(r.status_code) + " Error message:" + r.text
    handleErrorAndQuit(error, emailTo, reportType)
    
  temp = r.json()
  logRecords = temp["logRecords"]
  print(str(temp["totalRecords"]) + " records retrieved from circ log for given dates")

  itemIdList = []
  print("Counting circ log checkouts for the time period")
  count = 0
  for entry in logRecords:
    count += 1
    itemIdList.append(entry["items"][0]["itemId"])

  print(str(count) + " records retrieved from circ log")

  del logRecords

  count = collections.Counter(itemIdList)

  del itemIdList

  print("Attempting to get item data from inventory")

  itemResults = getItemRecords(emailAddr, offset, okapiURL, itemPath, limitItem, locationList, headers, callNumberStem, False, None, session)
  if itemResults == -1:
    error = "Cannot get item data from inventory"
    handleErrorAndQuit(error, emailTo, reportType)
  print("formatting report")
  itemData = "Item id, Location, Call Number, Title, Barcode, Created Date, folio Checkouts, Sierra Checkouts 2011 to 2021, Retention Policy\n"
  itemIds = []
  while itemResults:
    for item in itemResults:
      if item["id"] not in itemIds:
        itemIds.append(item["id"])
        if (("discoverySuppress" not in item) or (item["discoverySuppress"] != True) or (item["discoverySuppress"] == True and includeSuppressed == True)):
          retentionData = getRetentionDataFromHoldings(item, headers, session)
          print("logging checkout data for item " + item["id"])
          itemData = itemData + generateCheckoutEntry(item, count, retentionData)
    offset += 100
    print("Attempting to get next 100 records from offset " + str(offset))
    itemResults = getItemRecords(emailAddr, offset, okapiURL, itemPath, limitItem, locationList, headers, callNumberStem, False, None, session)
  print("CSV data ready")
  print(itemData)
  sendEmail.sendEmailWithAttachment(emailAddr, emailFrom, "Checkout Report", itemData)
  print('Report sent')
  print("Done, closing down")

def generateTemporaryLoanItem(emailAddr, locationList):
  print("starting")
  reportType="Item records with temporary loans"
  loanTypes = {"83eaaffa-6adf-4213-a154-33c53e3a550a":"3 hour reserve",
               "721d13ca-b5ae-4f63-8f75-22fbbb604058":"1 Week Reserve",
               "fda8ff4b-a389-4c15-955f-c10f0bc27b31":"24 Hour Course Reserve"}
  
  locationNames = {}
  for entry in locationList:
    locationNames[entry["id"]] = entry["name"]

  print(str(locationNames))
  session = requests.Session()

  retries = Retry(total=5, backoff_factor=0.1)
  session.mount('https://', HTTPAdapter(max_retries=retries))

  token = login.login()
  if token == 0:
    error = "Unable to log in to folio."
    handleErrorAndQuit(error, emailTo, reportType)

  headers = {'x-okapi-tenant': tenant, 'x-okapi-token': token}

  print("Attempting to retrieve item records with temporary loan types")

  path = "/item-storage/items"

  query = "&query=(temporaryLoanTypeId==83eaaffa-6adf-4213-a154-33c53e3a550a OR temporaryLoanTypeId==721d13ca-b5ae-4f63-8f75-22fbbb604058 OR temporaryLoanTypeId==fda8ff4b-a389-4c15-955f-c10f0bc27b31)"
  arrayName = "items"

  itemRecords = getAllFromEndPoint(path, query, arrayName, headers, session)

  if len(itemRecords) < 1:
    msg = "No item records with required loan types found."
    handleErrorAndQuit(msg, emailTo, reportType)
  print("Item records retrieved, parsing")
  csv = "title,barcode,loantype,templocation,permlocation,effectivelocation\n"
  for record in itemRecords:
    title = "\"" + getTitleforItem(record["id"], headers, session) + "\""
    locations = getLocationsFromHoldings(record["holdingsRecordId"], headers, session)
    permanent = "\"" + locationNames[locations["Permanent"]] + "\""
    effective = "\"" + locationNames[locations["Effective"]] + "\""
    if "Temporary" in locations:
      temporary = "\"" + locationNames[locations["Temporary"]] + "\""
    else:
      temporary = ""
    barcode = record["barcode"]
    loanType = "\"" + loanTypes[record["temporaryLoanTypeId"]] + "\""

    lineTuple = (title, barcode, loanType, temporary, permanent, effective)
    line = ",".join(lineTuple) + "\n"
    csv += line

  print(csv)
  print("Parsing done, attempting to send file")
  sendEmail.sendEmailWithAttachment(emailAddr, emailFrom, "Items on Temporary Loan Report", csv)
  print('Report sent')
  print("Done, closing down")

def generateNoCheckout(emailAddr, location, date):
  print("starting no checkout report")