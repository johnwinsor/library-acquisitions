## Installation

1. Clone repo
   - git clone git@github.com:johnwinsor/library-acquisitions.git
2. Install dependencies
   - uv sync
3. Activate virtual environment
   - `source .venv/bin/activate`
4. Create .env in src/library_acquisitions
    # Alma API Configuration
    # Replace with your actual API key from Ex Libris Developer Network
    ALMA_API_KEY=XXXXXXXXXXXXXXXXXXXXX

    # Alma API Base URL 
    # North America: https://api-na.hosted.exlibrisgroup.com
    # Europe: https://api-eu.hosted.exlibrisgroup.com  
    # Asia Pacific: https://api-ap.hosted.exlibrisgroup.com
    ALMA_BASE_URL=https://api-na.hosted.exlibrisgroup.com

    # WorldCat API Credentials
    WORLDCAT_API_KEY=xxxxxxxxxxxxxxxxxxxxx
    WORLDCAT_API_SECRET=xxxxxxxxxxxxxxxxxx

## Project Structure

library-acquisitions/           # Kebab-case for project root
├── .venv
├── amazon_orders/
│   └── 20250820/
│   ├── 20250920/
├── other_vendors/
├── pyproject.toml
├── uv.lock
├── README.md
├── src/
│   └── library_acquisitions/   # Snake_case for Python package
│       ├── __init__.py
│       ├── .env
│       ├── templates/
│           └── generic_book_template.json
│           ├── generic_films_template.json
│       ├── generic_pol_creator.py
│       ├── oclc_helpers.py
│       ├── alma_create_po_line.py
│       ├── amazon_pol_creator.py
└── docs/
└── tests/

## Alma PO Creation Processes

1. Amazon Orders
2. Generic Vendors (credit card orders)
   - Place order at vendor Website and print order summary or confimation.
   - Look up titles in OCLC WorldCat (https://search.worldcat.org/). Note OCLC numbers on order summary
   - Create new vendor in Alma if necessary
   - Create new working folder for order in other_orders/
     - Name after the vendor and append the date (hacky-labs_20250820)
   - `uv run generic-pol-creator`
3. JLG Shipments
4. EBSCO Renewals

## Alma/Workday Invoicing