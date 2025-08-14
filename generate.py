import requests
import folioAuthenticate
import sendEmail
from errorHandler import errorHandler
from config import okapiURL
from config import tenant
from config import emailFrom
from config import techSupportEmail
import collections
import re
from requests.adapters import HTTPAdapter, Retry

handleError = errorHandler()

logPath="/audit-data/circulation/logs"

itemPath = "/inventory/items"

holdingsPath = "/holdings-storage/holdings"

instancePath = "/instance-storage/instances"

locationsPath = "/locations"

session = requests.Session()
retries = Retry(total=5, backoff_factor=0.1)
session.mount('https://', HTTPAdapter(max_retries=retries))

def cleanLocationList(locationList):
  cleanList = []
  temp = ""
  for index, location in enumerate(locationList):
    temp = re.sub(r"[\'\'\[\]]", "", location)
    cleanList.append(temp)
  return cleanList

def concatenateLocations(locationList):
  locationString = ""
  for index,location in enumerate(locationList):
    locationString += location + ","
  return locationString

def getTitleforItem(itemid, session, email):
  headers = folioAuthenticate.getNewHeaders()
  url = okapiURL + "/inventory/items/" + itemid
  r = session.get(url, headers=headers)
  if r.status_code != 200:
    handleError.handleErrorAndQuit(errorHandler.constructHTTPErrorMessage(url, r))
  
  return r.json()["title"]

def getRecordById(id, path, session, email):
  headers = folioAuthenticate.getNewHeaders()
  url = okapiURL + path + id
  r = session.get(url, headers=headers)
  if r.status_code != 200:
    handleError.handleErrorAndQuit(errorHandler.constructHTTPErrorMessage(url, r))
  return r.json()

def getRetentionDataFromHoldings(itemRecord, session, email):
  holdingsId = itemRecord["holdingsRecordId"]
  path = "/holdings-storage/holdings/"
  json = getRecordById(holdingsId, path, session, email)
  if "retentionPolicy" in json:
    return "\"" + json["retentionPolicy"] + "\""
  else:
    return ""

def getLocationsFromHoldings(holdingsId, session, email):
  headers = folioAuthenticate.getNewHeaders()
  url = okapiURL + "/holdings-storage/holdings/" + holdingsId
  r = session.get(url, headers=headers)
  if r.status_code != 200:
    handleError.handleErrorAndQuit(errorHandler.constructHTTPErrorMessage(url, r))
  json = r.json()
  locations = {}
  locations["Permanent"] = json["permanentLocationId"]
  locations["Effective"] = json["effectiveLocationId"]
  if "temporaryLocationId" in json:
    locations["Temporary"] = json["temporaryLocationId"]
  return locations
  
def getAllFromEndPoint(path, queryString, arrayName, session, email):
  headers = folioAuthenticate.getNewHeaders()
  limit = "100"
  offset = 0

  fullQuery = "?limit=" + limit + "&offset=" + str(offset) + queryString
  url = okapiURL + path + fullQuery
  r = session.get(url, headers=headers)

  if r.status_code != 200:
    handleError.handleErrorAndQuit(errorHandler.constructHTTPErrorMessage(url, r))
  
  json = r.json()[arrayName]

  if len(json) < 1:
    return []
  itemList = {}
  for item in json:
    itemList[item["id"]] = item

  while json:
    offset += 100
    fullQuery = "?limit=" + limit + "&offset=" + str(offset) + queryString
    r = session.get(okapiURL + path + fullQuery, headers=headers)

    #request new auth token if neccessary
    if r.status_code == 401:
      headers = folioAuthenticate.getNewHeaders()
      r = session.get(okapiURL + path + fullQuery, headers=headers)
    
    json = r.json()[arrayName]
    if len(json) >= 1:
      for item in json:
        itemList[item["id"]] = item

  list = [*itemList.values()]

  return list

def generateReservesUse(email):
  reportType = "Reserves Use"
  params = None
  handleError.setParams(params)
  handleError.setReportType(reportType)
  handleError.setUserEmail(email)
  result = getAllFromEndPoint("/coursereserves/courses", "", "courses", session, email)
  
  if len(result) < 1:
    msg = "No reserves data found in reserves endpoint"
    handleError.handleErrorAndQuitNoTechEmail(msg)

  term = result[0]["courseListingObject"]["termObject"]

  startDate = term["startDate"]

  endDate = term["endDate"]

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

  result = getAllFromEndPoint("/locations", "", "locations", session, email)

  #format location data to list with id number as key
  locations = {}
  for entry in result:
    locations.update({entry["id"]: entry["name"]})

  #get start and end dates from reserves data
  result = getAllFromEndPoint("/coursereserves/reserves", "", "reserves", session, email)

  #combine course and item data into single entries
  reserveItems = []
  for entry in result:
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

  logQueryString = "&query=%28%28date%3E%3D%22" + startDate + "T00%3A00%3A00.000%22%20and%20date%3C%3D%22" + endDate + "T23%3A59%3A59.999%22%29%20and%20action%3D%3D%28%22Checked%20out*%22%29%29%20sortby%20date%2Fsort.descending"

  #get circ log data for date ranges
  result = getAllFromEndPoint(logPath, logQueryString, "logRecords", session, email)
  
  if len(result) < 1:
    error="No circulation data found for date ranges provided"
    handleError.handleErrorAndQuitNoTechEmail(error)

  itemIdList = []
  for entry in result:
    itemIdList.append(entry["items"][0]["itemId"])
  count = collections.Counter(itemIdList)
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

  sendEmail.sendEmailWithAttachment(email, emailFrom, "Checkout Report", itemData)

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


def getItemRecords(email, offset, okapiURL, itemPath, limitItem, locationList, callNumberStem, addStatus, cutoffDate, session):
  headers = folioAuthenticate.getNewHeaders()
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
  url = okapiURL + itemPath + itemQueryString
  r = session.get(url, headers=headers)
  if r.status_code != 200:
    handleError.handleErrorAndQuit(errorHandler.constructHTTPErrorMessage(url, r))
  

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


def generateCheckoutEntry(entry, checkoutCount, inhouseUseCount, retentionData):
  totalCheckout = "0"

  x = []
  x.append(entry["id"])
  x.append('"' + entry["effectiveLocation"]["name"] + '"')
  if "callNumber" in entry:
    x.append('"' + entry["callNumber"] + '"')
  else:
    x.append("")
  title = entry["title"].replace('"', '')
  title = title.replace('\'', '')
  x.append('"' + title + '"')
  if "barcode" in entry:
    x.append(entry["barcode"])
  else:
    x.append("")
  x.append(entry["metadata"]["createdDate"])
  if entry["id"] in checkoutCount:
    x.append(str(checkoutCount[entry["id"]]))
  else:
    x.append("0")
  if "notes" in entry:
    notes = entry["notes"]
    for note in notes:
      if note["itemNoteTypeId"] == "6d8bb43a-7455-4044-836e-f43740a4c38d":
        totalCheckout = note["note"]

  x.append(totalCheckout)

  if entry["id"] in inhouseUseCount:
    x.append(str(inhouseUseCount[entry["id"]]))
  else:
    x.append("0")

  x.append(retentionData)
  return ",".join(x) + "\n"


def generateInventoryReport(cutoffDate, locationList, email, callNumberStem):
  reportType = "Item Use Report"
  locationList = cleanLocationList(locationList)

  handleError.setReportType(reportType)
  handleError.setUserEmail(email)
  locationParams = concatenateLocations(locationList)
  params = {"cutoffDate":cutoffDate, "location List": locationParams,"Call Number Stem": callNumberStem}
  handleError.setParams(params)

  itemPath = "/inventory/items"

  limit = "100"

  offset = 0

  itemResults = getItemRecords(email, offset, okapiURL, itemPath, limit, locationList, callNumberStem, True, cutoffDate, session)

  itemData = "Item id, Location, Call Number, Title, Barcode, Status, Status Update Date\n"
  itemIds = []
  while itemResults:
    for item in itemResults:
      if item["id"] not in itemIds:
        itemIds.append(item["id"])
        if (("discoverySuppress" not in item) or (item["discoverySuppress"] != True)):
          itemData = itemData + generateInventoryEntry(item)
    offset += 100
    itemResults = getItemRecords(email, offset, okapiURL, itemPath, limit, locationList, callNumberStem, True, cutoffDate, session)

  sendEmail.sendEmailWithAttachment(email, emailFrom, "Inventory Report", itemData)

def generateCheckoutReport(startDate, endDate, locationList, email, includeSuppressed, callNumberStem): 
  reportType="Item use report"
  locationList = cleanLocationList(locationList)

  handleError.setReportType(reportType)
  handleError.setUserEmail(email)
  locationParams = concatenateLocations(locationList)
  params = {"startDate":startDate, "endDate":endDate, "location List": locationParams,"Call Number Stem": callNumberStem, "include Suppressed Records": str(includeSuppressed)}
  handleError.setParams(params)

  logQueryString = "&query=%28%28date%3E%3D%22" + startDate + "T00%3A00%3A00.000%22%20and%20date%3C%3D%22" + endDate + "T23%3A59%3A59.999%22%29%20and%20action%3D%3D%28%22Checked%20out*%22%29%29%20sortby%20date%2Fsort.descending"
 
  checkoutRecords = getAllFromEndPoint(logPath, logQueryString, "logRecords", session, email)

  checkoutItemIdList = []

  for entry in checkoutRecords:
    checkoutItemIdList.append(entry["items"][0]["itemId"])

  del checkoutRecords

  checkoutCount = collections.Counter(checkoutItemIdList)

  del checkoutItemIdList

  logQueryString = "&query=%28%28date%3E%3D%22" + startDate + "T00%3A00%3A00.000%22%20and%20date%3C%3D%22" + endDate + "T23%3A59%3A59.999%22%29%20and%20action%3D%3D%28%22Checked%20in*%22%29%29%20sortby%20date%2Fsort.descending"
  
  checkinRecords = getAllFromEndPoint(logPath, logQueryString, "logRecords", session, email)

  checkinItemIdList = []
  
  for record in checkinRecords:
    item = record["items"][0]
    if not record["linkToIds"] and "loanId" not in item:
      checkinItemIdList.append(item["itemId"])

  del checkinRecords

  inhouseUseCount = collections.Counter(checkinItemIdList)

  del checkinItemIdList
  offset = 0

  limitItem = "100"
  itemResults = getItemRecords(email, offset, okapiURL, itemPath, limitItem, locationList, callNumberStem, False, None, session)

  itemData = "Item id, Location, Call Number, Title, Barcode, Created Date, folio Checkouts, Sierra Checkouts 2011 to 2021, in-house use, Retention Policy\n"
  itemIds = []

  while itemResults:
    for item in itemResults:
      if item["id"] not in itemIds:
        itemIds.append(item["id"])
        if (("discoverySuppress" not in item) or (item["discoverySuppress"] != True) or (item["discoverySuppress"] == True and includeSuppressed == True)):
          retentionData = getRetentionDataFromHoldings(item, session, email)
          itemData = itemData + generateCheckoutEntry(item, checkoutCount, inhouseUseCount, retentionData)
    offset += 100
    itemResults = getItemRecords(email, offset, okapiURL, itemPath, limitItem, locationList, callNumberStem, False, None, session)

  sendEmail.sendEmailWithAttachment(email, emailFrom, "Checkout Report", itemData)

def generateTemporaryLoanItem(email, locationList):
  locationNames = {}
  for entry in locationList:
    locationNames[entry[0][0]] = entry[1]

  reportType="Item records with temporary loans"

  handleError.setReportType(reportType)
  handleError.setUserEmail(email)
  
  params = {"location List": str(locationNames)}
  handleError.setParams(params)

  loanTypes = {"83eaaffa-6adf-4213-a154-33c53e3a550a":"3 hour reserve",
               "721d13ca-b5ae-4f63-8f75-22fbbb604058":"1 Week Reserve",
               "fda8ff4b-a389-4c15-955f-c10f0bc27b31":"24 Hour Course Reserve"}
  
  path = "/item-storage/items"

  query = "&query=(temporaryLoanTypeId==83eaaffa-6adf-4213-a154-33c53e3a550a OR temporaryLoanTypeId==721d13ca-b5ae-4f63-8f75-22fbbb604058 OR temporaryLoanTypeId==fda8ff4b-a389-4c15-955f-c10f0bc27b31)"
  arrayName = "items"

  itemRecords = getAllFromEndPoint(path, query, arrayName, session, email)

  if len(itemRecords) < 1:
    msg = "No item records with required loan types found."
    handleError.handleErrorAndQuitNoTechEmail(msg)

  csv = "title,barcode,loantype,templocation,permlocation,effectivelocation\n"
  for record in itemRecords:
    title = "\"" + getTitleforItem(record["id"], session, email) + "\""
    locations = getLocationsFromHoldings(record["holdingsRecordId"], session, email)

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

  sendEmail.sendEmailWithAttachment(email, emailFrom, "Items on Temporary Loan Report", csv)

def generateNoCheckout(email, location, date):
  reportType="No checkout report"
  
  for character in disallowed_characters:
    location = location.replace(character, "")

  handleError.setReportType(reportType)
  handleError.setUserEmail(email)
  params = {"location": location}
  handleError.setParams(params)
  
  locationEntry = getRecordById(location, locationsPath + "/", session, email)
  locationName = locationEntry["name"]
  itemQuery = "&query=(status.name==\"Available\" and effectiveLocationId==" + location + " and metadata.updatedDate < " + date + ")"

  itemResults = getAllFromEndPoint(itemPath, itemQuery, "items", session, email)
 
  itemCSV = "itemId,Barcode,callNumber,location,status,title\n"
  for item in itemResults:
    id = item["id"]

    barcode = "none"
    callNumber = "none"
    callNumberComponents = item["effectiveCallNumberComponents"]
    if "barcode" in item:
      barcode = item["barcode"]
    if callNumberComponents["callNumber"] is not None:
      callNumber = callNumberComponents["callNumber"]
    title = getTitleforItem(item["id"], session, email)
    status = item["status"]["name"]
    line = id + "," + barcode + "," + callNumber + "," + locationName + "," + status + "," + title + "\n"
    itemCSV += line

  sendEmail.sendEmailWithAttachment(email, emailFrom, "No Checkout event report", itemCSV)



  



  