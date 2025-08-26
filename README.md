## Installation

1. Clone repo
   - git clone git@github.com:johnwinsor/library-acquisitions.git
2. Install dependencies
   - uv sync
3. Create .env in src/library_acquisitions
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