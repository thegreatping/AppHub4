"""Rush Check Request module.

Submit and track rush check requests through AP for urgent vendor payments.

Data store : SharePoint list on peakcampus.sharepoint.com/sites/BaseCampApps
List GUID  : b38a5488-e83e-4ab3-a888-ed7c3ca656b9
APP ID     : 19
Auth       : Graph API (item create/read) + SP REST API (attachments)

Required attachments per submission (3):
  1. Invoice copy
  2. RVP Approval
  3. Accountant Approval

Improvements over Power Apps version:
  - Single-page form with sections (no multi-step wizard friction)
  - Property selection auto-populates RM, RVP, and Accountant via AJAX
  - Running total auto-calculated from up to 4 GL line items
  - Check Amount vs. Total Amount validated client-side and server-side
  - FedEx PO Box warning shown contextually
  - Admin submission view with sortable columns
"""
from flask import Blueprint, render_template, session, jsonify, request
from auth import login_required
from modules import MODULES, APP_ID_MAP
import sys
from helpers import load_env, SafeConnection
from datetime import datetime

rush_check_bp = Blueprint("rush_check", __name__, url_prefix="/rush-check")

# ── Constants ────────────────────────────────────────────────────────────────────
APP_ID = 19
APP_NAME = "Rush Check Request"
SP_SITE_PATH = "peakcampus.sharepoint.com:/sites/BaseCampApps"
SP_SITE_BASE  = "https://peakcampus.sharepoint.com/sites/BaseCampApps"
SP_LIST_ID   = "b38a5488-e83e-4ab3-a888-ed7c3ca656b9"

# Shipping method choices (Choice field in SP)
SHIPPING_METHODS = [
    "Regular Mail",
    "FedEx Overnight",
    "FedEx 2nd Day",
    "Will Call / Pickup",
]

# US states for vendor address
US_STATES = [
    "AL","AK","AZ","AR","CA","CO","CT","DE","DC","FL","GA","HI","ID",
    "IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO",
    "MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA",
    "PR","RI","SC","SD","TN","TX","UT","VT","VI","VA","WA","WV","WI","WY",
]

# Full GL code list extracted from Power Apps source (identical list used across
# Rush Check, Special Handling, and Vendor Setup modules in the original app)
GL_CODES = [
    "4810-05 - Interest Income - Revolver Loan",
    "4810-06 - Interest Income - ACQ Loan",
    "4901-00 - Gain on Sale",
    "4902-00 - Sale Proceeds",
    "5002-01 - Third Party Accounting Fees",
    "5002-02 - Bank Fees",
    "5002-03 - Late Fees",
    "5002-04 - Payment Processing Fees",
    "5002-06 - Consulting/Professional Fees",
    "5002-08 - Food Expense - Infectious Disease",
    "5002-09 - Charge Card Billbacks",
    "5002-10 - Property System Software",
    "5003-00 - Franchise Tax",
    "5003-01 - Legal Expenses (Eviction Cost)",
    "5003-02 - Licenses & Permits",
    "5003-03 - Patent & Trademark Exp",
    "5003-04 - Risk and Compliance",
    "5003-06 - Sales/Use/Excise Tax Expense",
    "5003-09 - Annual Reports",
    "5003-10 - PST Expenses British Columbia",
    "5003-11 - PST Expenses Ontario",
    "5004-01 - Furniture Rentals",
    "5004-02 - Corporate Unit Houseware - Purchases",
    "5004-03 - Corporate Unit Houseware - Rentals",
    "5004-04 - Housing Supplies",
    "5005-01 - Office Equipment Purchase",
    "5005-02 - Office Equipment - Copiers",
    "5005-03 - Office Equip - Repairs and Maintenance",
    "5007-01 - Office Expenses/Supplies",
    "5007-02 - Printing",
    "5007-03 - Office Expense - Infectious Disease",
    "5008-00 - Offsite Storage",
    "5009-01 - Postage",
    "5009-02 - Overnight Mail",
    "5011-01 - Telephone Office",
    "5011-02 - Operations Technology",
    "5011-03 - Answering Service",
    "5011-04 - Cell Phones",
    "5011-06 - Conference Calls",
    "5011-07 - Internet - Employees",
    "5013-00 - Misc Office Expenses",
    "5013-01 - Professional Dev/Edu/Training",
    "5013-01 - Commissions",
    "5013-02 - Shoppers Reports",
    "5013-05 - Uniforms",
    "5013-06 - Dues & Subscriptions",
    "5013-07 - Payroll Service",
    "5015-00 - Public Relations",
    "5020-01 - Travel & Lodging",
    "5020-02 - Meals & Entertainment",
    "5020-03 - Air/Ground Transportation",
    "5020-04 - Temp Help Travel",
    "5020-05 - Vehicle/Shuttle Lease or Contract",
    "5020-06 - Vehicle Maintenance/Gas",
    "5020-07 - Parking/Tolls",
    "5030-00 - Office Rent",
    "5035-00 - Abandonded Pursuit",
    "5040-00 - Political Contributions/Lobbying",
    "5042-00 - Charitable Contributions",
    "5045-00 - Other Administrative Costs",
    "5045-01 - Misc Expense - Infectious Disease",
    "5101-05 - CA Payroll",
    "5101-12 - Office Employees",
    "5101-13 - Maintenance Employees",
    "5101-14 - Maintenance Labor Reimbursement",
    "5101-15 - Payroll Reimbursement",
    "5101-16 - Shuttle Employees",
    "5102-11 - Overtime Pay",
    "5103-00 - Bonuses & Commissions",
    "5103-03 - Employee Relations",
    "5103-04 - Tuition Reimbursement",
    "5104-00 - Temporary Help",
    "5105-00 - Salaries & Wages - Infectious Disease",
    "5106-00 - Benefits",
    "5106-01 - 401k Admin/Match/Audit",
    "5106-02 - Payroll Taxes",
    "5106-03 - Workers Compensation",
    "5106-05 - Insurance - Cobra",
    "5106-10 - Service and Leasing Reimbursement",
    "5107-00 - Employee Procurement",
    "5108-00 - Moving Expenses - Personnel",
    "5109-00 - Other Employee Expenses",
    "5201-00 - Resident Assistant Reimbursement",
    "5202-00 - Resident Programming",
    "5205-00 - Resident Advisor Programming",
    "5210-00 - Res Life Training",
    "5215-00 - Res Life Employee Expenses",
    "5220-00 - Resident Life Coordinator Programming",
    "5225-00 - Res Life Professional Development",
    "5230-00 - Res Life Operations",
    "5280-00 - Master Lease Expense - Landlord Contribution",
    "5285-00 - Master Lease Expense - Resident Assistant Stipends",
    "5301-00 - Write-Off Uncollectible",
    "5301-50 - Foregiveness of Debt",
    "5302-00 - Bad Debt Recovery",
    "5375-00 - Management Fees",
    "5380-00 - Asset Management Fees",
    "5401-00 - Print Media",
    "5402-00 - Direct Mail",
    "5402-03 - Outreach Marketing",
    "5402-04 - Conference Center Outreach Marketing",
    "5403-01 - Printing Expense (Direct Mailer)",
    "5405-03 - Collateral Materials",
    "5405-04 - Conference Center Collateral Materials",
    "5406-00 - Radio/TV/Billboard",
    "5408-00 - Internet-Property Website",
    "5408-01 - Internet Ads",
    "5408-02 - Internet- Marketing Tools",
    "5408-03 - Lead Tracking Solution",
    "5408-04 - Leasing Recruiters and Locators",
    "5408-05 - Conference Ctr Internet Ads",
    "5408-06 - Summer Internet Ads",
    "5409-00 - Resident Functions",
    "5409-03 - Model Decor",
    "5410-00 - Sponsorships/Memberships",
    "5411-00 - Signs/Bootlegs/Banners",
    "5413-00 - Newspaper",
    "5415-00 - Resident Recruitment/Retention",
    "5417-00 - Promotional Items",
    "5420-00 - Leasing Referrals",
    "5425-00 - Leasing Incentive-Infectious Disease",
    "5430-00 - Marketing & Leasing Consultants",
    "5440-00 - Trade Shows / Conferences",
    "5450-00 - Advertising/Marketing Other",
    "5450-01 - General Marketing Expense - Infectious Disease",
    "5501-01 - Telephone - Local for Residents",
    "5503-01 - Internet Provider",
    "5503-02 - Hardware",
    "5503-03 - Software Costs",
    "5503-74 - Repairs & Maint (3rd party)",
    "5509-00 - Misc Telecom Expenses",
    "5601-00 - Electricity",
    "5601-01 - Electricity - Common Areas",
    "5601-02 - Electricty - Occupied Units",
    "5601-03 - Electricity - Vacant Units",
    "5601-04 - Parking Lot Light Rental",
    "5603-00 - Gas",
    "5603-01 - Gas Common Area",
    "5603-02 - Gas Occupied Units",
    "5603-03 - Gas Vacant Units",
    "5604-00 - Water & Sewer",
    "5605-01 - Water - Clubhouse/Office/Buildings",
    "5606-00 - Cable",
    "5609-00 - Utility Billings",
    "5712-00 - Mail Service",
    "5713-01 - Exterminator",
    "5713-02 - Termite Bond",
    "5714-01 - Trash Removal",
    "5714-02 - Compactor Rental",
    "5715-00 - Other Outside Services",
    "5716-00 - Electric Vehicle Charging Station Expense",
    "5717-00 - Snow Removal Contract",
    "5720-00 - Security/Locks/Safety",
    "5721-00 - Security/Fire Monitoring",
    "5726-00 - Fire Extinguisher",
    "5727-00 - Security Personnel - Contract",
    "5728-00 - Food Service Expense",
    "5730-00 - Amenities",
    "5731-01 - Pool Contract",
    "5732-50 - Athletic Courts",
    "5734-00 - Fitness Room",
    "5736-00 - Clubhouse Amenities & Maint",
    "5736-05 - Tanning Facility & Equip",
    "5740-00 - Cleaning Service",
    "5742-00 - Cleaning Supplies",
    "5742-01 - Cleaning Other - Infectious Disease",
    "5743-00 - Concrete Walks & Curbs",
    "5744-00 - Parking Lot",
    "5745-00 - Ice/Snow Removal",
    "5746-00 - Breezeway Repairs",
    "5747-00 - Mailboxes",
    "5750-00 - Other Common Area Maint/Rpr",
    "5760-00 - Landscaping",
    "5761-00 - Landscape Contract",
    "5762-00 - Landscape Supplies",
    "5769-00 - Landscape Other",
    "5770-00 - Maintenance Supplies",
    "5770-01 - R&M Other - Infectious Disease",
    "5770-02 - Medical Supplies - Infectious Disease",
    "5771-00 - Facilities Uniform Expense",
    "5772-00 - Equipment Repair/Rental",
    "5774-00 - Elevator Maintenance",
    "5775-00 - Pool Repairs/Supplies",
    "5780-00 - Appliance Parts & Service",
    "5785-00 - Appliance Repair and Maintenance",
    "5790-00 - HVAC",
    "5800-00 - Plumbing Repair",
    "5810-00 - Electrical Repair",
    "5820-00 - Flooring",
    "5823-00 - Carpet - Cleaning",
    "5830-00 - Vinyl/Ceramic Tile",
    "5840-00 - Counter Top/Cabinet",
    "5850-00 - Walls, Windows & Doors",
    "5860-00 - Outside Building Maintenance & Signs",
    "5861-00 - Recoverable Signage",
    "5862-00 - Painting",
    "5865-00 - Roof Repairs",
    "5869-00 - Other Building Maintenance",
    "5870-00 - Non-Turn Damage Billbacks",
    "5871-00 - Maintenance Parts Reimbursements",
    "5872-00 - Maintenance Reimbursement",
    "5911-00 - Furniture Repair",
    "5912-00 - Walls/Doors/Windows",
    "5913-00 - Turn Painting",
    "5915-00 - Turn Housekeeping/Linen Service",
    "5916-00 - Floor Coverings Repair/Repl (Turn)",
    "5917-00 - Turn Carpet Cleaning and Repair",
    "5918-00 - Turn Cleaning Contracts",
    "5919-00 - Cleaning Supplies",
    "5920-00 - Security Gates",
    "5921-00 - Common Area",
    "5922-00 - Other Turnover/Recoverable Costs",
    "5923-00 - Turn Trash or Dumpster Expense",
    "5950-00 - Turn Cleaning Fees Billing",
    "5951-00 - Turn Damage Fees Billing",
    "6001-00 - Real Property Tax",
    "6001-05 - Property Tax Adjustment",
    "6002-00 - Personal Property Tax",
    "6003-00 - Insurance",
    "6003-01 - Insurance - General and Professional Liability",
    "6003-02 - Insurance - Other",
    "6003-05 - Auto Insurance",
    "6003-06 - Insurance - Corp, Other",
    "6003-10 - Insurance - Corp WC",
    "6003-12 - Corp Prop, GL, Umb",
    "6003-15 - Insurance - Corp crime",
    "6003-20 - Insurance - Corp D&O, EPL, FId",
    "6003-21 - Insurance - Corp Auto",
    "6003-25 - Insurance Corp E&O",
    "6003-40 - Insurance - Claims Deductibles",
    "6004-00 - PMI",
    "6005-00 - Suspended Capital",
    "6010-00 - Non-Recurring Maintenance",
    "6010-50 - Expense Due to Infectious Disease",
    "6015-00 - Temp Help Travel-BV",
    "6101-00 - Interest Expense",
    "6101-05 - Member Interest",
    "6101-10 - Member Interest - Deferred",
    "6102-00 - Mezzanine Interest",
    "6102-01 - Mezzanine Interest - Deferred",
    "6102-05 - Interest Expense Acquisition Loan",
    "6103-00 - Other Interest Expense",
    "6103-01 - Interest Expense Development Fee",
    "6104-00 - Interest Expense - Lease",
    "6105-00 - Bond Interest Expense",
    "6105-01 - Swap Fees",
    "6106-00 - Bond Fees Expense",
    "6106-01 - Loan Fees Expense",
    "6106-02 - LOC Fee Expense - Prior Year",
    "6106-03 - Loan Expense",
    "6106-04 - Bond Trustee Fees",
    "6106-05 - LOC Fees",
    "6109-00 - Financing Costs",
    "6110-00 - Unrealized Gain(Loss)",
    "6110-01 - Realized Gain(Loss)",
    "6110-02 - Unrealized Incentive Fees",
    "6200-10 - Retail/Commercial Admin",
    "6200-11 - Retail/Commercial Payroll",
    "6200-12 - Retail/Commercial Adv/Marketing",
    "6200-13 - Retail/Commercial Telecom",
    "6200-14 - Retail/Commercial Electric",
    "6200-15 - Retail/Commercial Water",
    "6200-16 - Retail/Commercial Trash",
    "6200-17 - Retail/Commercial Snow Removal",
    "6200-18 - Retail/Commercial Security",
    "6200-19 - Retail/Commercial Landscape",
    "6200-20 - Retail/Commercial R&M",
    "6200-21 - Retail/Commercial Insurance",
    "6200-22 - Retail/Commercial Tenant Improvements",
    "6200-23 - Retail/Commercial Management Fee",
    "6200-24 - Retail/Commercial Real Estate Taxes",
    "6200-25 - Retail/Commercial Exterminator",
    "6200-26 - Retail/Commercial Lease Payment",
    "6200-27 - Retail/Commercial Bad Debt",
    "6200-28 - Retail/Commercial Parking Mgt Company",
    "6200-29 - Retail/Commercial Infectious Disease",
    "6200-30 - Retail/Commercial Tenant Specific Expense",
    "6200-31 - Retail/Commercial Tenant Specific Billback",
    "6200-32 - Retail/Commercial Gas",
    "6301-00 - Ground Lease",
    "6501-00 - Building Depreciation",
    "6501-01 - Depreciation Ex-Lease",
    "6501-02 - Depreciation Exp - Land Improvements",
    "6501-03 - Depreciation Exp - Bldg Imprmnts",
    "6502-00 - Depreciation Exp - FF&E",
    "6502-05 - Amortization Exp - Tenant Imprmnts",
    "6503-00 - Automobiles",
    "6503-05 - Depreciation Expense",
    "6504-00 - Amortization",
    "6504-01 - Amortization - Software",
    "6504-02 - Amortization - Lease Costs & Commission",
    "6504-03 - Amortization - Organization Costs",
    "6504-04 - Amortization - Acquisition Costs",
    "6504-05 - Amortization In Place Lease Value",
    "6504-06 - Amortization - Loan Costs",
    "6505-00 - Bond Fees Amortization",
    "6506-00 - Gain or Loss on Asset Disposal",
    "6600-00 - Cost of Sales",
    "6700-00 - Selling Expenses",
    "6701-00 - Third Party Real Estate Commissions",
    "6702-00 - Closing Costs",
    "6705-00 - Organization Costs",
    "6710-00 - Acquisition/Transition Costs",
    "6715-00 - Development Period Expenses",
    "7001-00 - Cap. Ex. FF&E",
    "7002-00 - Cap. Ex. Building",
    "7003-00 - Cap Ex - Blinds & Window Coverings",
    "7004-00 - Cap Ex - Appliances",
    "7005-00 - HVAC",
    "7006-00 - Carpets & Flooring",
    "7007-00 - Safety & Security",
    "7008-00 - Amenities",
    "7009-00 - Keys & Locks",
    "7010-00 - Vehicles",
    "7011-00 - FF&E (non-unit)",
    "7012-00 - Safety & Security",
    "7013-00 - Landscaping",
    "7014-00 - Fences & Gates",
    "7015-00 - Roofs",
    "7016-00 - Computers",
    "7017-00 - Lighting",
    "7018-00 - Parking Lots & Sidewalks",
    "7019-00 - Signage",
    "7099-00 - Contra Cap Ex",
    "7100-00 - Miscellaneous",
    "7100-05 - Rent Expense",
    "7100-06 - Rent Expense Offset",
    "7100-07 - Reserve-Exterior Maintenance",
    "7100-08 - Reserve Future Maintenance",
    "7100-09 - Reserve-Future Roadway",
    "7100-10 - Reserve Reimbursement",
    "7100-70 - Partnership Audit & Tax Fees",
    "7100-71 - Business License/Taxes",
    "7100-80 - Partnership Legal Expenses",
    "7100-90 - Shuttle Expense",
    "7101-00 - Miscellaneous Exp/Adj",
    "7102-00 - Prior Year Adjustments",
    "7103-00 - NOI Performance Bonus",
    "7104-00 - Bonus Accrual",
    "7105-00 - Fund Level Expense Push Down",
    "7107-00 - Inc/Loss from JV's",
    "7108-00 - Partnership Expenses",
    "7109-00 - Asset Management T&E",
    "7111-00 - Loan Costs",
    "7301-00 - Extraordinary Loss",
    "7302-00 - Extraordinary Gain",
    "7303-00 - Other Income",
    "7305-00 - State Tax Expense",
    "7305-01 - Federal Income Tax",
    "7420-00 - FAS 34 Interest Expense",
    "700000 - Capital Projects - Properties",
    "700100 - Computer Lab",
    "700110 - Computer Lab-FF Upgrades",
    "700200 - Fitness Center",
    "700210 - Fitness Center-FF Upgrades",
    "700300 - Theater",
    "700310 - Theater-FF Upgrades",
    "700400 - Game Room",
    "700410 - Game Room-FF Upgrades",
    "700500 - Leasing Space/Area",
    "700510 - Leasing Space/Area-FF Upgrades",
    "700600 - Study Rooms",
    "700610 - Study Rooms-FF Upgrades",
    "700800 - Design Fee",
    "700810 - Blueprints and copies",
    "700820 - Architect",
    "710100 - Pool Enhancement",
    "710200 - Pool Resurface",
    "710300 - Tennis Court",
    "710400 - Basketball Court",
    "710500 - Sand Volleyball Court",
    "710600 - Exterior Picnic Areas",
    "710700 - Raquetball Court",
    "710800 - Other Outdoor Amenity Areas",
    "710850 - Other Outdoor Building Improvements",
    "710900 - Other Outdoor FF&E",
    "715100 - Paint",
    "715200 - Wood Repairs",
    "715300 - Tuck Pointing",
    "715400 - Siding",
    "715410 - Powerwashing",
    "715500 - Flat Roof Repairs",
    "715510 - Flat Roof Replacement",
    "715600 - Tile Roof Repairs",
    "715610 - Tile Roof Replacements",
    "715700 - Roof Repairs",
    "715710 - Roof Replacements",
    "715900 - Roof Other",
    "720100 - Parking Lot Striping",
    "720110 - Parking Lot Asphalt",
    "720120 - Parking Lot Skin Coat",
    "720200 - Landscape Architect",
    "720210 - Landscape Clean-up",
    "720220 - Landscape Upgrade",
    "720230 - Landscape Tree/Brush Removal",
    "720300 - Parking Garage",
    "720400 - Exterior Lighting",
    "720500 - Side Walk Repairs",
    "720590 - Other Concrete Repairs",
    "720600 - Exterior Doors",
    "720700 - Site Drainage",
    "720800 - Signage",
    "730100 - Flooring",
    "730150 - Painting",
    "730200 - Appliances",
    "730250 - Water Damage",
    "730300 - Fixtures",
    "730350 - Cabinets",
    "730400 - Countertops",
    "730450 - Interior Doors",
    "730500 - Furniture",
    "730550 - Ice Maker",
    "730600 - Blinds",
    "730800 - Unit convert to electronic system locks",
    "730810 - Unit install bedroom door locks",
    "730820 - Windows",
    "730840 - Screens",
    "730850 - Dryer Vents",
    "730860 - Abatement",
    "730870 - Unit Interior Upgrades - Other",
    "735100 - Elevator",
    "735200 - Interior Hallways - Painting",
    "735210 - Interior Hallways - Fixtures",
    "735220 - Interior Hallways-Flooring",
    "735230 - Interior Hallways-Furniture",
    "735300 - Vent Fans",
    "735310 - Exhaust Fans",
    "735320 - Intake Fan",
    "735400 - Abatement",
    "740100 - Heating/Cooling",
    "740200 - Chiller/Boiler",
    "740300 - Air Handling Units",
    "740400 - Fan Coils",
    "740500 - Riser",
    "740600 - Boiler Automation System",
    "740700 - Dual Temperature Pump",
    "740800 - R-22 to 410a Conversion",
    "740900 - Clean HVAC Units",
    "601100 - Bank Fees",
    "601101 - Payment Processing Fees",
    "601105 - Insurance",
    "601110 - License & Permits",
    "601120 - Property Systems Software",
    "601130 - Office Equipment Repair & Maintenance",
    "601140 - Furniture Rental",
    "601150 - Office Supplies",
    "601160 - Postage",
    "601170 - Overnight Mail",
    "601180 - Telephone - Local",
    "601190 - Telephone - Long Distance",
    "601200 - Answering Service",
    "601210 - Office Internet",
    "601220 - Professional Dev/Edu/Training",
    "601230 - Shoppers Reports",
    "601240 - Uniforms",
    "601250 - Lodging",
    "601260 - Meals and Entertainment",
    "601270 - Air/Ground Transportation",
    "601280 - Vehicle Maintenance/Gas",
    "601290 - Other Administrative Costs",
    "601300 - Management Fees",
    "601400 - Prepaid GST/HST",
    "605100 - Office Employees",
    "605110 - Maintenance Employees",
    "605120 - Overtime",
    "605130 - Bonuses",
    "605140 - Other Compensation",
    "605150 - Employee Relations",
    "605160 - Payroll Taxes & Benefits",
    "605170 - Temporary Help",
    "605180 - Contract Labor",
    "605200 - Other Employee Expenses",
    "605210 - Payroll Taxes",
    "605220 - Benefits",
    "605230 - 401K",
    "605240 - Workers Comp",
    "605250 - Employee Procurement",
    "610100 - Print Ads",
    "610110 - Flyers",
    "610120 - Direct Mailers",
    "610130 - Marketing Collateral",
    "610140 - Radio Ads",
    "610145 - Internet Ads",
    "610150 - Internet WebPage",
    "610155 - Signs Bootlegs and Banners",
    "610160 - Property/Office/Clubhouse Promotion",
    "610165 - LeadTrack Solution - Leasehawk",
    "610170 - Postage and Distribution",
    "610180 - Food",
    "610190 - Travel",
    "610210 - Promotional Items",
    "610220 - Leasing Incentives",
    "610230 - Production Charges",
    "610240 - Resident Recruitment and Retention",
    "610250 - Resident Functions",
    "610260 - Sponsorships and Memberships",
    "610270 - Leasing Referrals",
    "610280 - Advertising/Marketing Other",
    "615100 - Internet Provider",
    "615110 - Hardware & Installation",
    "615120 - Cable",
    "615140 - Repair and Maintenance/3rd Party",
    "620100 - Electricity",
    "620110 - Water & Sewer",
    "620120 - Gas",
    "625100 - Exterminator",
    "625110 - Trash Removal",
    "625120 - Other Outside Services",
    "625130 - Common Area Cleaning",
    "625140 - Snow Removal",
    "630100 - Security and Fire Systems",
    "630110 - Security Personnel",
    "635100 - Landscape Supplies",
    "635110 - Landscape Other",
    "690100 - Start Up Costs",
    "690110 - Renderings",
    "690120 - Leasing Signage",
    "690130 - Floor Plans",
    "690140 - Fence Banner",
    "690150 - Mktg Collateral (Start Up)",
    "690160 - Computers Copier Purchase Etc.",
    "690165 - Brand & Website Development",
    "690170 - Temp Space Rent-Trailer",
    "690180 - Temp Space Rent-Retail",
    "690190 - System Startup Cost",
    "690200 - Office (Staff) Furniture",
    "690210 - Temp Space Build out",
    "690220 - Model Setup",
    "690230 - Leasing Space Decor",
    "690240 - Office Supplies (Startup)",
    "690250 - Phone System Purchase",
    "690260 - Security and Fire Systems Install",
    "690270 - Maintenance Shop Setup",
    "690280 - Key Trak Machine",
    "690998 - Peak Startup Fee",
    "R&R Reserves Funded Internally",
    "R&R Reserves Funded with Lender",
    "Retail - Leasing Commissions",
    "Retail - Tenant Improvements",
]

_env = None


def _get_env():
    global _env
    if _env is None:
        _env = load_env()
    return _env


def _require_access():
    if session.get("is_developer"):
        return None
    user_modules = session.get("user_modules", [])
    for m in user_modules:
        if m["id"] == APP_ID:
            return None
    return jsonify({"error": "unauthorized"}), 403


def _is_admin():
    if session.get("is_developer"):
        return True
    user = session.get("user", {})
    email = user.get("email", "").lower()
    if not email:
        return False
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    cur = conn.execute(
        "SELECT COUNT(*) FROM dbo.APP_ADMINS WHERE APP_ID = ? AND LOWER(ADMIN_EMAIL) = ?",
        [APP_ID, email],
    )
    return cur.fetchone()[0] > 0


def _get_shell_context():
    from config import APP_VERSION
    user_modules = session.get("user_modules", [])
    allowed_string_ids = set()
    for m in user_modules:
        string_id = APP_ID_MAP.get(m["id"])
        if string_id:
            allowed_string_ids.add(string_id)
    visible = [m for m in MODULES if m["id"] in allowed_string_ids] if user_modules else MODULES
    return dict(
        modules=visible,
        active_module="rush_check_request",
        user=session.get("user", {}),
        is_developer=session.get("is_developer", False),
        is_dev_mode=session.get("is_dev_mode", False),
        is_impersonating=session.get("is_impersonating", False),
        impersonating_user=session.get("impersonating_user", None),
        version=APP_VERSION,
    )


def _sp():
    from graph_client import get_site_id
    return get_site_id(SP_SITE_PATH), SP_LIST_ID


# ─── PAGE ROUTE ──────────────────────────────────────────────────────────────────

@rush_check_bp.route("/")
@login_required
def index():
    check = _require_access()
    if check:
        return check
    ctx = _get_shell_context()
    ctx["is_admin"] = _is_admin()
    ctx["shipping_methods"] = SHIPPING_METHODS
    ctx["us_states"] = US_STATES
    ctx["gl_codes"] = GL_CODES
    return render_template("rush_check.html", **ctx)


# ─── API: PROPERTIES ─────────────────────────────────────────────────────────────

@rush_check_bp.route("/api/properties", methods=["GET"])
@login_required
def api_properties():
    check = _require_access()
    if check:
        return check
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    cur = conn.execute("""
        SELECT PROPERTY_NAME, RM_NAME, RM_EMAIL, RVP_NAME, RVP_EMAIL,
               ACCOUNTANT, ENTITY_NUMBER
        FROM dbo.PROPERTY_0
        WHERE FLAG_REPORTABLE = 1
          AND FLAG_DISPOSITIONED = 0
          AND ADDRESS_COUNTRY = 'US'
        ORDER BY PROPERTY_NAME
    """)
    rows = cur.fetchall()
    return jsonify([{
        "name":         r[0],
        "rm_name":      r[1] or "",
        "rm_email":     r[2] or "",
        "rvp_name":     r[3] or "",
        "rvp_email":    r[4] or "",
        "accountant":   r[5] or "",
        "entity_number": r[6] or "",
    } for r in rows])


# ─── API: GL CODES ────────────────────────────────────────────────────────────────

@rush_check_bp.route("/api/gl-codes", methods=["GET"])
@login_required
def api_gl_codes():
    check = _require_access()
    if check:
        return check
    return jsonify(GL_CODES)


# ─── API: SUBMIT ─────────────────────────────────────────────────────────────────

@rush_check_bp.route("/api/submit", methods=["POST"])
@login_required
def api_submit():
    check = _require_access()
    if check:
        return check

    # ── Collect form fields ─────────────────────────────────────────────────────
    f = request.form

    property_name = (f.get("property") or "").strip()
    rm_name       = (f.get("rm_name") or "").strip()
    rm_email      = (f.get("rm_email") or "").strip()
    rvp_name      = (f.get("rvp_name") or "").strip()
    rvp_email     = (f.get("rvp_email") or "").strip()
    accountant    = (f.get("accountant") or "").strip()
    entity_id1    = (f.get("entity_id1") or "").strip()
    vendor_name   = (f.get("vendor_name") or "").strip()
    vendor_id     = (f.get("vendor_id") or "").strip()
    street_address = (f.get("street_address") or "").strip()
    vendor_city   = (f.get("vendor_city") or "").strip()
    vendor_state  = (f.get("vendor_state") or "").strip()
    vendor_zip    = (f.get("vendor_zip") or "").strip()
    invoice_number = (f.get("invoice_number") or "").strip()
    date_needed   = (f.get("date_needed") or "").strip()
    shipping_method = (f.get("shipping_method") or "").strip()
    special_instructions = (f.get("special_instructions") or "").strip()
    check_amount_raw = (f.get("check_amount") or "0").strip()
    authorization = (f.get("authorization") or "").strip()

    # Line items 1-4
    line_items = []
    for i in range(1, 5):
        eid  = (f.get(f"entity_id{i}") or "").strip()
        gl   = (f.get(f"gl_code{i}") or "").strip()
        desc = (f.get(f"description{i}") or "").strip()
        amt  = (f.get(f"amount{i}") or "0").strip()
        line_items.append({"entity_id": eid, "gl_code": gl, "description": desc, "amount": amt})

    # ── Server-side validation ──────────────────────────────────────────────────
    required = {
        "Property": property_name,
        "Vendor Name": vendor_name,
        "Vendor ID": vendor_id,
        "Vendor Street Address": street_address,
        "Vendor City": vendor_city,
        "Vendor State": vendor_state,
        "Vendor Zip": vendor_zip,
        "Invoice Number": invoice_number,
        "Date Needed": date_needed,
        "Shipping Method": shipping_method,
        "Check Amount": check_amount_raw,
    }
    for label, val in required.items():
        if not val:
            return jsonify({"error": f"{label} is required."}), 400

    if not authorization:
        return jsonify({"error": "Authorization acknowledgment is required."}), 400

    if shipping_method not in SHIPPING_METHODS:
        return jsonify({"error": "Invalid shipping method."}), 400

    try:
        check_amount = round(float(check_amount_raw), 2)
    except ValueError:
        return jsonify({"error": "Check Amount must be a number."}), 400

    # Validate line items: at least 1 complete row required
    try:
        amounts = [round(float(li["amount"]), 2) for li in line_items]
    except ValueError:
        return jsonify({"error": "All Amount fields must be numeric."}), 400

    total = round(sum(amounts), 2)
    if total == 0:
        return jsonify({"error": "At least one line item with an amount is required."}), 400

    # For each line item with a non-zero amount, require entity_id, gl_code, description
    for i, li in enumerate(line_items, 1):
        if amounts[i - 1] > 0:
            if not li["entity_id"]:
                return jsonify({"error": f"Entity ID {i} is required when Amount {i} is entered."}), 400
            if not li["gl_code"]:
                return jsonify({"error": f"GL Code {i} is required when Amount {i} is entered."}), 400
            if not li["description"]:
                return jsonify({"error": f"Description {i} is required when Amount {i} is entered."}), 400

    if round(check_amount, 2) != round(total, 2):
        return jsonify({"error": f"Check Amount (${check_amount:,.2f}) must equal the sum of line item amounts (${total:,.2f})."}), 400

    # Validate 3 required attachment files
    invoice_file   = request.files.get("attach_invoice")
    rvp_file       = request.files.get("attach_rvp")
    accountant_file = request.files.get("attach_accountant")

    if not invoice_file or not invoice_file.filename:
        return jsonify({"error": "Invoice attachment is required."}), 400
    if not rvp_file or not rvp_file.filename:
        return jsonify({"error": "RVP Approval attachment is required."}), 400
    if not accountant_file or not accountant_file.filename:
        return jsonify({"error": "Accountant Approval attachment is required."}), 400

    # ── Format date for SP (ISO 8601) ───────────────────────────────────────────
    try:
        dt = datetime.strptime(date_needed, "%Y-%m-%d")
        date_needed_iso = dt.strftime("%Y-%m-%dT00:00:00Z")
    except ValueError:
        return jsonify({"error": "Invalid Date Needed format."}), 400

    # ── Build SP fields payload ─────────────────────────────────────────────────
    user = session.get("user", {})
    submitter_name  = user.get("name", "")
    submitter_email = user.get("email", "")

    from config import APP_VERSION
    sp_fields = {
        "Submittedby":         submitter_name,
        "Property":            property_name,
        "RM":                  rm_name,
        "RVP":                 rvp_name,
        "PropertyAccountant":  accountant,
        "RMEmail":             rm_email,
        "RVPEmail":            rvp_email,
        "Vendor":              vendor_name,
        "VendorID":            vendor_id,
        "StreetAddress":       street_address,
        "VendorCity":          vendor_city,
        "VendorState_x002f_Province": vendor_state,
        "VendorZip_x002f_PostalCode": vendor_zip,
        "InvoiceNumber":       invoice_number,
        "DateNeeded":          date_needed_iso,
        "ShippingMethod":      {"Value": shipping_method},
        "CheckAmount":         check_amount,
        "EntityID1":           line_items[0]["entity_id"],
        "GLCode1":             line_items[0]["gl_code"],
        "Description1":        line_items[0]["description"],
        "Amount1":             amounts[0],
        "Total":               total,
        "Authorization":       authorization,
        "Status":              False,
        "SubmittedEmail":      submitter_email,
    }

    # Optional fields (blank lines / special instructions)
    if special_instructions:
        sp_fields["SpecialInstructions"] = special_instructions
    for i in range(1, 4):  # lines 2-4
        if amounts[i] > 0:
            sp_fields[f"EntityID{i+1}"]    = line_items[i]["entity_id"]
            sp_fields[f"GLCode{i+1}"]      = line_items[i]["gl_code"]
            sp_fields[f"Description{i+1}"] = line_items[i]["description"]
            sp_fields[f"Amount{i+1}"]      = amounts[i]

    # ── Create SP list item ─────────────────────────────────────────────────────
    try:
        from graph_client import create_item, add_sp_attachment
        site_id, list_id = _sp()
        created = create_item(site_id, list_id, sp_fields)
        item_id = created.get("_item_id", "")
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
    except Exception as exc:
        return jsonify({"error": f"SharePoint error creating item: {exc}"}), 500

    # ── Upload attachments via SP REST API ──────────────────────────────────────
    attach_errors = []
    for label, file_obj, safe_prefix in [
        ("Invoice", invoice_file, "invoice"),
        ("RVP Approval", rvp_file, "rvp_approval"),
        ("Accountant Approval", accountant_file, "accountant_approval"),
    ]:
        try:
            import os
            ext = os.path.splitext(file_obj.filename)[1]
            dest_name = f"{safe_prefix}{ext}"
            add_sp_attachment(SP_SITE_BASE, SP_LIST_ID, item_id, dest_name, file_obj.read())
        except Exception as exc:
            attach_errors.append(f"{label}: {exc}")

    if attach_errors:
        return jsonify({
            "success": True,
            "warning": "Request submitted but some attachments failed to upload: " + "; ".join(attach_errors),
        })

    return jsonify({"success": True, "message": "Rush Check Request submitted successfully."})


# ─── API: SUBMISSIONS (admin) ─────────────────────────────────────────────────────

@rush_check_bp.route("/api/submissions", methods=["GET"])
@login_required
def api_submissions():
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin access required"}), 403

    try:
        from graph_client import list_items
        site_id, list_id = _sp()
        rows = list_items(site_id, list_id)
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503
    except Exception as exc:
        return jsonify({"error": f"SharePoint error: {exc}"}), 500

    results = []
    for row in rows:
        shipping = row.get("ShippingMethod") or {}
        results.append({
            "id":              row.get("_item_id", ""),
            "submitted_by":    row.get("Submittedby", ""),
            "property":        row.get("Property", ""),
            "vendor":          row.get("Vendor", ""),
            "vendor_id":       row.get("VendorID", ""),
            "invoice_number":  row.get("InvoiceNumber", ""),
            "date_needed":     row.get("DateNeeded", ""),
            "shipping_method": shipping.get("Value", "") if isinstance(shipping, dict) else str(shipping),
            "check_amount":    row.get("CheckAmount", 0),
            "total":           row.get("Total", 0),
            "status":          row.get("Status", False),
            "submitted_email": row.get("SubmittedEmail", ""),
            "created":         row.get("Created", ""),
            "rm":              row.get("RM", ""),
            "rvp":             row.get("RVP", ""),
        })

    results.sort(key=lambda x: x["created"], reverse=True)
    return jsonify(results)


# ─── API: IS ADMIN ────────────────────────────────────────────────────────────────

@rush_check_bp.route("/api/is_admin", methods=["GET"])
@login_required
def api_is_admin():
    check = _require_access()
    if check:
        return check
    return jsonify({"is_admin": _is_admin()})


# ─── API: ADMINS ──────────────────────────────────────────────────────────────────

@rush_check_bp.route("/api/admins", methods=["GET"])
@login_required
def api_admins():
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin access required"}), 403
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    cur = conn.execute("""
        SELECT ID, ADMIN_EMAIL, DATE_CREATED
        FROM dbo.APP_ADMINS
        WHERE APP_ID = ?
        ORDER BY ID
    """, [APP_ID])
    return jsonify([{"id": r[0], "email": r[1], "created": str(r[2])} for r in cur.fetchall()])


@rush_check_bp.route("/api/admins", methods=["POST"])
@login_required
def api_add_admin():
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin access required"}), 403
    data = request.get_json()
    email = (data.get("email") or "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"error": "Valid email required"}), 400
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    conn.execute(
        "INSERT INTO dbo.APP_ADMINS (APP_ID, APP_NAME, ADMIN_EMAIL, DATE_CREATED) VALUES (?,?,?,GETDATE())",
        [APP_ID, APP_NAME, email],
    )
    return jsonify({"success": True})


@rush_check_bp.route("/api/admins/<int:admin_id>", methods=["DELETE"])
@login_required
def api_remove_admin(admin_id):
    check = _require_access()
    if check:
        return check
    if not _is_admin():
        return jsonify({"error": "admin access required"}), 403
    env = _get_env()
    conn = SafeConnection(env, "DB_APP_SUPPORT", None, direct=True)
    conn.execute("DELETE FROM dbo.APP_ADMINS WHERE ID = ? AND APP_ID = ?", [admin_id, APP_ID])
    return jsonify({"success": True})
