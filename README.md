# Folio Reporting App

## Overview
The reporting app is a program written in python using the flask web framework (https://flask.palletsprojects.com/en/stable/).  It's designed to be run over the Folio (https://folio.org/) back-end APIs, especially the ones in mod-inventory (https://github.com/folio-org/mod-inventory) and mod-inventory-storage (https://github.com/folio-org/mod-inventory-storage).  The app's function is to fill a variety of reporting needs not currently addressed by Folio, including:

1. Checkout reports based on call number, date and location, typically used for weeding projects
2. Checkout reports for physical reserve items, often used to persuade instructors to do virtual reserves (physical reserves tend to get very low use)
3. An inventory report used to help locate items missing from the shelf
4. A temporary loan report, used to find records that have a temporary loan currently set
5. A no-checkout activity report, used to find any items that have no checkout activity, which is also used for weeding.

## Accessing the reports app

Accessing the app requires the URL to the app on our server as well as a password.  These can be obtained from the Head of Systems and Discovery.

## Using the app

Once you've accessed the app and logged in, you'll be presented with a screen allowing you to choose the type of report to run.  Choose the report you want to run, and you'll be presented with an options screen, which varies depending on the type of report you want to run.

Because it can take a very long time to run reports (hours or days in some cases), all reports are emailed to you by the app when completed.  All report options screens will ask you for the email for the final report to be sent to.  Depending on how large the report is, the app may need to split the report into several files (this is because campus caps the size of email attachments).  If it needs to send you more than one file, it will number the emails sequentially (1 of 2, 2 of 2, etc.)

If you do not see your report, check your spam folder-these are system-generated emails, they do look like spam to filters.

If no items are found in the system that match your report criteria, the resulting report will be blank.  If you are getting blank reports, tweak your report criteria.

## Types of reports explained

### Checkout report

The checkout report generates a list of items and the number of times they've been checked out in the time period specified.

The checkout report allows you to limit the report based on the time period you want to see checkout activity for, location of the item, and/or call number stem.  

The app does not support true call number range searching-whatever call number (or part of a call number) you use will be searched for as a stem-any item with a call number that begins with that stem will be included.  You cannot enter a range of call numbers.  

You must enter at least one location, OR a call number stem.  You do not have to include both, just one or the other.  

You can choose multiple locations by using shift or command click (depending on wether you're using a Mac or PC).

The screen pre-loads with the time constraints set to the date we adopted Folio to the present day.  Be aware thet the more locations you choose, or wider the date range, the longer the report will take to run.  You are advised to split up large reports by year and/or location.

By default, suppressed records are not included in the report.  There is a checkbox you can use to tell the app to include them.

#### Checkout report fields

**ItemId:**  the UUID of the item record in Folio  
**Location:** the item's permanent location  
**Call Number:** the item's call number  
**Title:** self-explanatory  
**Barcode:** the assigned barcode  
**Created date:** the date and time the item record was created  
**Folio Checkouts:** the number of checkout events that took place during the time window you specified.  If there were none, the number will be 0.  
**Sierra Checkouts 2011 to 2021:**  Data on item checkouts for this item in Sierra, our previous ILS. These are stored in the item notes field, and are included on every report generated.  Because they are text, they can't be included/excluded based on date, which is why they're included on every report run.  
**In-house use:**  any stats on in-house use for this item, if they exist for the item and time period specified  
**Retention policy:** links/notes regarding retention policies for this item-this is useful if you're using this report for weeding  

## Reserves use report

This generates a report of the number of times physical items that are currently on reserve were checked out, measuring from the time they were put on reserve to the current day.

This report can ONLY give you use data for currently-reserved physical items.

### Reserves report fields

**ItemId:**  the UUID of the item record in Folio  
**Location:** the item's permanent location  
**Barcode:** the item's barcode  
**Title:** self-explanatory  
**Course name:** the name of the course the item is on reserve for  
**Instructor name:** the name of the instructor who put the item on reserve  
**Course code:** the course catalog code for the course the item is on reserve for  
**Folio checkout events:** thenumber of times the item has been checked out so far this semester  

## Inventory Report

The inventory report is used to locate lost books or other physical items.  The report requires either a call number stem OR one or more locations, similar to the checkout report.

The form also asks for a cut-off date.  The report will contain items that DO NOT have any check-in events AFTER that date.  The idea is that when staff are starting to do a shelf inventory, they note the date they start, then they go through the shelves and check-in any items on the shelf.  Any items that should be in that area that DON'T have check-in activity since that date are not on the shelf.

### Inventory Report Fields

Again, items showing in this report HAVE NOT had any CHECK-IN events since the specified cut-off date.

**Item id:** the UUID of the item record in Folio  
**Location:** location of the item  
**Call Number, Title, Barcode:**	Should require no explanation  
**Status:** The current status of this item in Folio-available, checked-out, etc.  
**Status Update Date:** The date/time the item was moved to the current status.  If the item has never been checked out, this will match the date the item record was created in the system  

## Temporary Loan Report

This part of the app generates a list of all items that currently have a loan policy set to either 24-hour loan, 3-hour loan, or one-week loan.  These items tend to be temporarily set to these loan periods because they are on reserve.

Like the reserve activity report, this will only show you items that currently have these loan policies set.

### Temporary Loan Report Fields

**title &	barcode:** Should be self-explanatory  	
**loantype:** the currently set temporary loan type  
**templocation:**  These items also tend to have temporary locations because they are on reserve.  This field tells you what that location is currently set to.  
**permlocation:** the item's permanent location  
**effectivelocation:**  the item's Current effective location.  This will be the temporary location if one is set.  Otherwise it should be the item's permanent location  

## No checkout report

This report will scan for items in specific area that are currently listed as "Available" and have no checkout activity since the cut-off date specified.  This is useful for weeding projects.

You may not choose multiple locations for this report.  If you need that, you will need to run multiple reports.

By default, the form is loaded with the date we adopted Folio.  Because checkout data from before that date is stored in text fields in the item record, it's not searchable, and so data from that time is not available from this report.

### No checkout report fields

**itemId:** the UUID of the item record in Folio	
**Barcode,	callNumber,	location, title :** Self-explanatory
**status:** Curreent status of the item (should be "available")

