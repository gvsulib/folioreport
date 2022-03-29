import requests
import login
import sys
import sendEmail
from config import okapiURL
from config import tenant
from config import emailFrom
import collections

logPath="/audit-data/circulation/logs"

emailTo = ""

def getAllFromEndPoint(path, queryString, arrayName, headers):
  limit = "100"
  offset = 0

  fullQuery = "?limit=" + limit + "&offset=" + str(offset) + queryString

  r = requests.get(okapiURL + path + fullQuery, headers=headers)
  print("Attempting to get data from endpoint: " + path)
  if r.status_code != 200:
    error = "Could not get data from endpoint, status code: " + str(r.status_code) + " Error message:" + r.text
    print(error)
    sendEmail.sendEmail(emailTo, emailFrom, error, "Error Generating checkout report")
    sys.exit()
  json = r.json()[arrayName]

  if len(json) < 1:
    error = "No data defined in " + path + " endpoint"
    print(error)
    sendEmail.sendEmail(emailTo, emailFrom, error, "Error Generating reserves report")
    sys.exit()
  
  list = json

  while json:
    offset += 100
    fullQuery = "?limit=" + limit + "&offset=" + str(offset) + queryString
    print("attempting to fetch next 100 entries from " + str(offset))
    r = requests.get(okapiURL + path + fullQuery, headers=headers)
    json = r.json()[arrayName]
    if len(json) >= 1:
      list = list + json
    else:
      print("No more data to fetch")
  return list


def generateReservesUse(emailAddr):

  emailTo = emailAddr
  
  token = login.login()
  if token == 0:
    error = "Unable to log in to folio."
    print(error)
    sendEmail.sendEmail(emailTo, emailFrom, error, "Error Generating reserves report")
    sys.exit()

  reservesPath = "/coursereserves/reserves"
  arrayName = "reserves"
  query = ""
  headers = {'x-okapi-tenant': tenant, 'x-okapi-token': token}
  print("Attempting to get course and instructor data")
  result = getAllFromEndPoint("/coursereserves/courses", "", "courses", headers)
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
  result = getAllFromEndPoint("/locations", "", "locations", headers)
  print("Location data retrieved")

  #format location data to list with id number as key
  locations = {}
  for entry in result:
    locations.update({entry["id"]: entry["name"]})

  #get start and end dates from reserves data
  print("Getting listing of reserve items")
  result = getAllFromEndPoint("/coursereserves/reserves", "", "reserves", headers)

  #combine course and item data into single entries
  reserveItems = []
  for entry in result:
    location = ""
    if "temporaryLocationId" in entry["copiedItem"]:
      location = entry["copiedItem"]["temporaryLocationId"]
    elif "permanentLocationId" in entry["copiedItem"]:
      location = entry["copiedItem"]["permanentLocationId"]

    locationText = locations[location]

    itemEntry = {
      "id": entry["itemId"],
      "title":entry["copiedItem"]["title"],
      "barcode": entry["copiedItem"]["barcode"],
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

  logQueryString = "&query=%28%28date%3E%3D%22" + startDate + "T00%3A00%3A00.000%22%20and%20date%3C%3D%22" + endDate + "T23%3A59%3A59.999%22%29%20and%20action%3D%3D%28%22Checked%20out%22%29%29%20sortby%20date%2Fsort.descending"

  #get circ log data for date ranges
  result = getAllFromEndPoint(logPath, logQueryString, "logRecords", headers)
  print("Data from circ logs retrieved")
  itemIdList = []
  print("Counting circ log checkouts for the time period: " + startDate + " to " + endDate)
  for entry in result:
    itemIdList.append(entry["items"][0]["itemId"])
  count = collections.Counter(itemIdList)
  print("collating data for final report to CSV")
  itemData = "Item id, title, Barcode, location, course name, course code, instructor, checkout events\n"

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

def getItemRecords(email, offset, okapiURL, itemPath, limitItem, locationList, headers):
  locationQuery = ""
  
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
    json = r.json()
    return json["items"]

def generateEntry(entry, count):
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
  return ",".join(x) + "\n"


def generateReport(startDate, endDate, locationList, emailAddr, includeSuppressed): 
  disallowed_characters = "''[]"

  for index, location in enumerate(locationList):
    for character in disallowed_characters:
      location = location.replace(character, "")
    locationList[index] = location

  token = login.login()
  if token == 0:
      error = "Unable to log in to folio."
      print(error)
      sendEmail.sendEmail(emailAddr, emailFrom, error, "Error Generating checkout report")
      sys.exit()
    

  itemPath = "/inventory/items"

  limitLog = "100000"

  limitItem = "100"

  offset = 0
  
  logQueryString = "?limit=" + limitLog + "&offset=0&query=%28%28date%3E%3D%22" + startDate + "T00%3A00%3A00.000%22%20and%20date%3C%3D%22" + endDate + "T23%3A59%3A59.999%22%29%20and%20action%3D%3D%28%22Checked%20out*%22%29%29%20sortby%20date%2Fsort.descending"
  print("query string: " + okapiURL + logPath + logQueryString)
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

  itemData = "Item id, Location, Call Number, Title, Barcode, Created Date, Number of Checkouts, Total Checkouts\n"

  while itemResults:
    for item in itemResults:
      if (("discoverySuppress" not in item) or (item["discoverySuppress"] != True) or (item["discoverySuppress"] == True and includeSuppressed == True)):
        print("logging checkout data for item " + item["id"])
        itemData = itemData + generateEntry(item, count)
    offset += 100
    print("Attempting to get next 100 records from offset " + str(offset))
    itemResults = getItemRecords(emailAddr, offset, okapiURL, itemPath, limitItem, locationList, headers)



  print("CSV data ready")

  sendEmail.sendEmailWithAttachment(emailAddr, emailFrom, "Checkout Report", itemData)
  print('Report sent')
  print("Done, closing down")


  





















