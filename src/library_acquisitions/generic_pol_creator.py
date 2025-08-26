#!/usr/bin/env python

"""
Generic PO Line Creator with Templates and Enhanced UI
Creates Alma PO Line JSON files using templates and rich interactive interface

This script provides a template-based system for creating Alma purchase order lines
with conditional logic for receiving note categories and smart user interface.
"""

import json
import os
import sys
import glob
from datetime import datetime, timedelta
import re

import questionary
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Try to import OCLC helpers - graceful fallback if not available
try:
    from .oclc_helpers import search_oclc_metadata, is_oclc_available, validate_oclc_number
    OCLC_AVAILABLE = True
except ImportError:
    OCLC_AVAILABLE = False

console = Console()

# =============================================================================
# TEMPLATE MANAGEMENT
# =============================================================================

def find_templates_directory():
    """
    Find the templates directory by checking multiple possible locations.
    
    This handles various project structures and deployment scenarios,
    including uv project layouts and direct script execution.
    
    Returns:
        str|None: Path to templates directory if found, None otherwise
    """
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Search locations in order of preference
    possible_locations = [
        # Same directory as script
        os.path.join(script_dir, "templates"),
        # Current working directory
        os.path.join(os.getcwd(), "templates"),
        # Parent directory of script
        os.path.join(os.path.dirname(script_dir), "templates"),
        # uv project structure
        os.path.join(script_dir, "..", "..", "src", "libraryacquisitions", "templates"),
        # Environment variable override
        os.environ.get('TEMPLATES_DIR', '')
    ]
    
    for location in possible_locations:
        if location and os.path.exists(location):
            console.print(f"✅ Found templates directory: {location}", style="green")
            return location
    
    return None

def load_templates():
    """
    Load all available JSON templates from the templates directory.
    
    Templates should be JSON files containing complete PO line structures
    with optional metadata fields (_description, _template_version).
    
    Returns:
        dict: Dictionary mapping template names to template data
    """
    templates_dir = find_templates_directory()
    
    if not templates_dir:
        console.print("❌ Templates directory not found!", style="bold red")
        console.print("Searched in:")
        console.print("  - Same directory as script")
        console.print("  - Current working directory")
        console.print("  - Parent directory of script")
        console.print("  - Project structure paths")
        console.print("\nYou can also set TEMPLATES_DIR environment variable to specify the location.")
        return {}
    
    templates = {}
    template_files = glob.glob(os.path.join(templates_dir, "*.json"))
    
    if not template_files:
        console.print(f"❌ No .json template files found in {templates_dir}", style="bold red")
        return {}
    
    # Load each template file
    for template_file in template_files:
        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                template_name = os.path.splitext(os.path.basename(template_file))[0]
                templates[template_name] = json.load(f)
                console.print(f"✅ Loaded template: {template_name}", style="green")
        except Exception as e:
            console.print(f"⚠️ Error loading {template_file}: {str(e)}", style="yellow")
    
    return templates

def select_template(templates):
    """
    Present template selection interface with descriptions.
    
    Args:
        templates (dict): Available templates from load_templates()
        
    Returns:
        tuple|None: (template_name, template_data) or None if cancelled
    """
    if not templates:
        console.print("❌ No templates available!", style="bold red")
        return None
    
    # Create rich choice display with template metadata
    choices = []
    for template_name, template in templates.items():
        desc = template.get('_description', 'No description')
        material_type = template.get('material_type', {}).get('value', 'Unknown')
        vendor = template.get('vendor', {}).get('value', 'Unknown')
        
        choice_text = f"{template_name} - {desc} ({material_type}, {vendor})"
        choices.append(questionary.Choice(choice_text, value=template_name))
    
    template_name = questionary.select(
        "Select a template:",
        choices=choices,
        style=questionary.Style([
            ('question', 'fg:#ff0066 bold'),
            ('answer', 'fg:#44ff00 bold'),
            ('pointer', 'fg:#ff0066 bold'),
            ('highlighted', 'fg:#ff0066 bold bg:#000044'),
        ])
    ).ask()
    
    if template_name:
        return template_name, templates[template_name]
    return None

# =============================================================================
# USER INPUT COLLECTION
# =============================================================================

def get_user_input():
    """
    Collect basic bibliographic and order information from user.
    
    This function handles the core order data that's needed for every PO line,
    with optional OCLC WorldCat integration to pre-populate bibliographic fields.
    
    Returns:
        dict: User input data for order processing
    """
    # Valid reporting codes (subjects) for institutional use
    subjects = [
        'Archives', 'Architecture', 'Art', 'Biology', 'Book Art', 'Business',
        'Chemistry', 'Communications', 'Computer Science', 'Cooking', 'Dance',
        'Data Science', 'Economics', 'Education', 'English Language Studies',
        'Entrepreneurship', 'Environmental Science', 'Ethnic Studies', 'Fiction',
        'Game Design', 'General', 'General Science', 'Graphic Novels',
        'Health Sciences', 'History', 'Juvenile', 'Library Science', 'Mathematics',
        'Music', 'Philosophy', 'Poetry', 'Political Science', 'Psychology',
        'Public Policy', 'Religion', 'Sociology', 'Theatre', 'WGSS'
    ]
    
    console.print(Panel.fit("📝 Enter Order Information", style="bold blue"))
    
    # === VENDOR INFORMATION ===
    vendor_code = questionary.text(
        "Vendor code (e.g., hacky-m):",
        validate=lambda text: len(text.strip()) > 0 or "Vendor code is required"
    ).ask()
        
    vendor_account = questionary.text(
        "Vendor account (e.g., hacky-m):",
        validate=lambda text: len(text.strip()) > 0 or "Vendor account is required"
    ).ask()
    
    vendor_ref = questionary.text("Vendor reference/invoice number:").ask()
    
    # === OPTIONAL OCLC SEARCH ===
    oclc_data = {}
    used_oclc_number = None  # Track the OCLC number for system_control_number
    
    if OCLC_AVAILABLE and is_oclc_available():
        use_oclc = questionary.confirm(
            "Search OCLC WorldCat for bibliographic data? (Recommended - saves typing)"
        ).ask()
        
        if use_oclc:
            oclc_number = questionary.text(
                "Enter OCLC number:",
                validate=lambda text: validate_oclc_number(text) if text.strip() else "OCLC number is required"
            ).ask()
            
            if oclc_number:
                console.print("Searching OCLC WorldCat...", style="yellow")
                oclc_data = search_oclc_metadata(oclc_number)
                
                if oclc_data:
                    # Store the OCLC number for later use
                    used_oclc_number = oclc_data.get('oclc_number')
                    console.print("✅ Found bibliographic data from OCLC!", style="green")
                    
                    # Show what was found
                    found_fields = []
                    for field, value in oclc_data.items():
                        if value and field != 'oclc_number':  # Don't show OCLC number in this list
                            found_fields.append(f"{field}: {value}")
                    
                    if found_fields:
                        console.print("Retrieved:", style="cyan")
                        for field in found_fields:
                            console.print(f"  • {field}")
                else:
                    console.print("⚠️ No data found for that OCLC number", style="yellow")
    
    # === BIBLIOGRAPHIC INFORMATION ===
    # Pre-populate with OCLC data if available, otherwise prompt user
    title = questionary.text(
        "Title:",
        default=oclc_data.get('title', ''),
        validate=lambda text: len(text.strip()) > 0 or "Title is required"
    ).ask()
    
    author = questionary.text(
        "Author (optional):",
        default=oclc_data.get('author', '')
    ).ask()
    
    # === OPTIONAL BIBLIOGRAPHIC DETAILS ===
    isbn = questionary.text(
        "ISBN (optional):",
        default=oclc_data.get('isbn', ''),
        validate=lambda text: validate_isbn(text) if text.strip() else True
    ).ask()
    
    publisher = questionary.text(
        "Publisher (optional):",
        default=oclc_data.get('publisher', '')
    ).ask()
    
    publication_year = questionary.text(
        "Publication year (optional):",
        default=oclc_data.get('publication_year', ''),
        validate=lambda text: validate_year(text) if text.strip() else True
    ).ask()
    
    # === ORDER INFORMATION ===
    price = questionary.text(
        "Price (e.g., 25.99):",
        validate=validate_price
    ).ask()
    
    # === QUANTITY SELECTION ===
    quantity_choice = questionary.select(
        "Quantity:",
        choices=[
            questionary.Choice("1", 1),
            questionary.Choice("2", 2),
            questionary.Choice("3", 3),
            questionary.Choice("4", 4),
            questionary.Choice("5", 5),
            questionary.Choice("Other", "other")
        ]
    ).ask()
    
    if quantity_choice == "other":
        quantity = questionary.text(
            "Enter quantity:",
            validate=lambda text: text.isdigit() and int(text) > 0 or "Must be a positive number"
        ).ask()
        quantity = int(quantity)
    else:
        quantity = quantity_choice
    
    # === REPORTING CODE ===
    reporting_code = questionary.autocomplete(
        "Reporting code (required):",
        choices=subjects,
        validate=lambda text: text in subjects or f"Please select a valid subject from the list"
    ).ask()
    
    return {
        'vendor_code': vendor_code or '',
        'vendor_account': vendor_account or '',
        'title': title or '',
        'author': author or '',
        'price': price or '',
        'vendor_reference_number': vendor_ref or '',
        'isbn': isbn or '',
        'publisher': publisher or '',
        'publication_year': publication_year or '',
        'quantity': quantity,
        'reporting_code': reporting_code or '',
        'oclc_number': used_oclc_number  # Include OCLC number if available
    }

def get_receiving_note_categories():
    """
    Handle receiving note category selection with conditional data collection.
    
    This implements the business logic for receiving note categories:
    - Users can select multiple categories (except "None")
    - "None" is exclusive (cannot be combined with others)
    - Certain selections trigger additional data collection
    
    Returns:
        tuple: (category_string, conditional_data)
            - category_string: Pipe-delimited string for Alma receiving note
            - conditional_data: Dict of additional data collected based on selections
    """
    console.print(Panel.fit("📝 Receiving Note Categories", style="bold blue"))
    
    categories = [
        "None",
        "Note", 
        "Interested User",
        "Reserve",
        "Display",
        "Replacement"
    ]
    
    selected_categories = questionary.checkbox(
        "Select receiving note categories (use spacebar to select, enter to confirm):",
        choices=categories,
        validate=validate_receiving_categories
    ).ask()
    
    # Handle "None" selection
    if not selected_categories or "None" in selected_categories:
        return "None", {}
    
    # Create pipe-delimited string for Alma
    category_string = " | ".join(selected_categories)
    
    # === CONDITIONAL DATA COLLECTION ===
    conditional_data = {}
    
    # Collect interested user details if selected
    if "Interested User" in selected_categories:
        console.print("\n🔹 Interested User selected - collecting user details...", style="cyan")
        
        user_id = questionary.text(
            "User ID (9 digits):",
            validate=validate_user_id
        ).ask()
        
        notify = questionary.confirm("Notify user on receiving activation?").ask()
        hold = questionary.confirm("Hold item for user?").ask()
        
        conditional_data['interested_user'] = {
            'user_id': user_id,
            'notify': notify,
            'hold': hold
        }
    
    # Collect additional notes if "Note" selected
    if "Note" in selected_categories:
        console.print("\n🔹 Note selected - collecting additional notes...", style="cyan")
        
        additional_notes = questionary.text("Additional notes:").ask()
        conditional_data['additional_notes'] = additional_notes or ''
    
    # Collect reserve details if "Reserve" selected
    if "Reserve" in selected_categories:
        console.print("\n🔹 Reserve selected - collecting reserve details...", style="cyan")
        
        reserve_note = questionary.text("Reserve note (optional):").ask()
        conditional_data['reserve_note'] = reserve_note or ''
    
    return category_string, conditional_data

# =============================================================================
# VALIDATION FUNCTIONS
# =============================================================================

def validate_price(text):
    """Validate price format and value."""
    if not text.strip():
        return "Price is required"
    
    try:
        price = float(text.strip())
        return price > 0 or "Price must be greater than 0"
    except ValueError:
        return "Please enter a valid price (e.g., 25.99)"

def validate_isbn(text):
    """Basic ISBN format validation."""
    if not text.strip():
        return True
    
    # Remove hyphens and spaces, keep only alphanumeric
    clean_isbn = ''.join(char for char in text if char.isalnum())
    
    if len(clean_isbn) not in [10, 13]:
        return "ISBN should be 10 or 13 digits"
    
    return True

def validate_year(text):
    """Validate publication year range."""
    try:
        year = int(text.strip())
        if 1400 <= year <= 2030:
            return True
        return "Year should be between 1400 and 2030"
    except ValueError:
        return "Please enter a valid year"

def validate_user_id(text):
    """Validate user ID format (exactly 9 digits)."""
    if len(text.strip()) == 9 and text.strip().isdigit():
        return True
    return "User ID must be exactly 9 digits"

def validate_receiving_categories(selected):
    """Validate receiving note category selections."""
    if not selected:
        return "Please select at least one category"
    
    if "None" in selected and len(selected) > 1:
        return "Cannot select 'None' with other categories"
    
    return True

# =============================================================================
# DATA PROCESSING
# =============================================================================

def customize_template(template, user_input, receiving_categories, conditional_data):
    """
    Apply user input and conditional data to the selected template.
    
    This function transforms the template into a complete PO line JSON
    by populating it with user data and handling conditional logic.
    
    Args:
        template (dict): Base template structure
        user_input (dict): Basic order information
        receiving_categories (str): Pipe-delimited category string
        conditional_data (dict): Additional data based on category selections
        
    Returns:
        dict: Complete PO line data ready for Alma API
    """
    # Create deep copy to avoid modifying original template
    po_data = json.loads(json.dumps(template))
    
    # Remove template metadata (not needed in final JSON)
    po_data.pop('_description', None)
    po_data.pop('_template_version', None)
    
    # === VENDOR INFORMATION ===
    po_data['vendor']['value'] = user_input['vendor_code']
    po_data['vendor_account'] = user_input['vendor_account']
    
    # === BIBLIOGRAPHIC METADATA ===
    if 'resource_metadata' not in po_data:
        po_data['resource_metadata'] = {}
    
    po_data['resource_metadata']['title'] = user_input['title']
    
    if user_input['author']:
        po_data['resource_metadata']['author'] = user_input['author']
    
    if user_input['isbn']:
        po_data['resource_metadata']['isbn'] = user_input['isbn']
    
    if user_input['publisher']:
        po_data['resource_metadata']['publisher'] = user_input['publisher']
    
    if user_input['publication_year']:
        po_data['resource_metadata']['publication_year'] = user_input['publication_year']
    
    # Add OCLC number as system control number if available
    if user_input.get('oclc_number'):
        po_data['resource_metadata']['system_control_number'] = [user_input['oclc_number']]
    
    # === PRICING ===
    # Format price to ensure consistent decimal places
    price = user_input['price']
    try:
        price_float = float(price)
        price = f"{price_float:.2f}"
    except ValueError:
        pass  # Keep as-is if conversion fails
    
    po_data['price'] = {
        "sum": price,
        "currency": {"value": "USD"}
    }
    
    # Update fund distribution with same price
    if 'fund_distribution' in po_data and po_data['fund_distribution']:
        po_data['fund_distribution'][0]['amount'] = {
            "sum": price,
            "currency": {"value": "USD"}
        }
    
    # === ORDER DETAILS ===
    if user_input['vendor_reference_number']:
        po_data['vendor_reference_number'] = user_input['vendor_reference_number']
    
    # Update quantity in location
    if 'location' in po_data and po_data['location']:
        po_data['location'][0]['quantity'] = user_input['quantity']
    
    # === RECEIVING NOTE ===
    # Set receiving note to the category string
    if receiving_categories != "None":
        po_data['receiving_note'] = receiving_categories
    else:
        po_data['receiving_note'] = ""
    
    # === CONDITIONAL DATA HANDLING ===
    # Handle notes based on category selections
    notes = []
    
    if 'additional_notes' in conditional_data and conditional_data['additional_notes']:
        notes.append({"note_text": conditional_data['additional_notes']})
    
    if 'reserve_note' in conditional_data and conditional_data['reserve_note']:
        notes.append({"note_text": "Reserve Note: " + conditional_data['reserve_note']})
    
    if notes:
        po_data['note'] = notes
    
    # Handle interested user if selected
    if 'interested_user' in conditional_data:
        user_info = conditional_data['interested_user']
        po_data['interested_user'] = [{
            "primary_id": user_info['user_id'],
            "notify_receiving_activation": user_info['notify'],
            "hold_item": user_info['hold'],
            "notify_renewal": False,
            "notify_cancel": False
        }]
    else:
        # Remove interested_user if not needed
        po_data.pop('interested_user', None)
    
    # === SYSTEM FIELDS ===
    # Set expected receipt date (30 days from now)
    expected_date = datetime.now() + timedelta(days=30)
    po_data['expected_receipt_date'] = expected_date.strftime('%Y-%m-%d')
    
    # Set reporting code (subject)
    if user_input['reporting_code']:
        po_data['reporting_code'] = user_input['reporting_code']
    
    return po_data

def generate_filename(user_input):
    """
    Generate descriptive filename for the JSON output.
    
    Creates a filename with title, vendor reference, and timestamp
    to make files easily identifiable.
    
    Args:
        user_input (dict): User input data containing title and vendor reference
        
    Returns:
        str: Generated filename for JSON output
    """
    # Clean title for filesystem safety
    clean_title = re.sub(r'[^\w\s-]', '', user_input['title'])
    clean_title = re.sub(r'\s+', '_', clean_title.strip())
    clean_title = clean_title[:30]  # Limit length
    
    # Add timestamp for uniqueness
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Clean vendor reference
    vendor_ref = user_input.get('vendor_reference_number', 'noref')
    clean_vendor_ref = re.sub(r'[^\w-]', '', vendor_ref)[:15]
    
    return f"generic_{clean_title}_{clean_vendor_ref}_{timestamp}.json"

def save_po_file(po_data, filename):
    """
    Save PO line data to JSON file with proper formatting.
    
    Args:
        po_data (dict): Complete PO line data
        filename (str): Target filename
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(po_data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        console.print(f"❌ Error saving file: {str(e)}", style="bold red")
        return False

# =============================================================================
# DISPLAY FUNCTIONS
# =============================================================================

def display_summary(po_data, filename, receiving_categories, conditional_data):
    """
    Display comprehensive summary of the created PO line.
    
    Shows all relevant information in a formatted table for user review
    before saving the file.
    
    Args:
        po_data (dict): Complete PO line data
        filename (str): Target filename
        receiving_categories (str): Selected categories string
        conditional_data (dict): Additional collected data
    """
    table = Table(title="📋 Order Summary", show_header=True, header_style="bold magenta")
    table.add_column("Field", style="cyan", width=20)
    table.add_column("Value", style="white", width=50)
    
    # === CORE ORDER INFORMATION ===
    title = po_data.get('resource_metadata', {}).get('title', 'N/A')
    author = po_data.get('resource_metadata', {}).get('author', 'Not specified')
    price = po_data.get('price', {}).get('sum', 'N/A')
    vendor = po_data.get('vendor', {}).get('value', 'N/A')
    vendor_account = po_data.get('vendor_account', 'N/A')
    material_type = po_data.get('material_type', {}).get('value', 'N/A')
    vendor_ref = po_data.get('vendor_reference_number', 'Not specified')
    quantity = po_data.get('location', [{}])[0].get('quantity', 'N/A')
    reporting_code = po_data.get('reporting_code', 'N/A')
    receiving_note = po_data.get('receiving_note', 'Not specified')
    
    # Add core rows
    table.add_row("Title", title)
    table.add_row("Author", author)
    table.add_row("Price", f"${price}")
    table.add_row("Vendor", vendor)
    table.add_row("Vendor Account", vendor_account)
    table.add_row("Material Type", material_type)
    table.add_row("Vendor Reference", vendor_ref)
    table.add_row("Quantity", str(quantity))
    table.add_row("Subject", reporting_code)
    table.add_row("Receiving Note", receiving_note)
    
    # === OPTIONAL BIBLIOGRAPHIC FIELDS ===
    isbn = po_data.get('resource_metadata', {}).get('isbn', '')
    if isbn:
        table.add_row("ISBN", isbn)
    
    publisher = po_data.get('resource_metadata', {}).get('publisher', '')
    if publisher:
        table.add_row("Publisher", publisher)
    
    # Show OCLC number if present
    system_control_numbers = po_data.get('resource_metadata', {}).get('system_control_number', [])
    if system_control_numbers:
        oclc_display = ', '.join(system_control_numbers)
        table.add_row("OCLC Number", oclc_display)
    
    # === CONDITIONAL DATA DISPLAY ===
    if 'interested_user' in conditional_data:
        user_info = conditional_data['interested_user']
        user_text = f"{user_info['user_id']} (notify: {user_info['notify']}, hold: {user_info['hold']})"
        table.add_row("Interested User", user_text)
    
    if 'additional_notes' in conditional_data and conditional_data['additional_notes']:
        table.add_row("Additional Notes", conditional_data['additional_notes'])
    
    if 'reserve_note' in conditional_data and conditional_data['reserve_note']:
        table.add_row("Reserve Note", conditional_data['reserve_note'])
    
    # === FILE INFORMATION ===
    table.add_row("File", filename)
    
    console.print(table)

# =============================================================================
# MAIN APPLICATION FLOW
# =============================================================================

def main():
    """
    Main application entry point.
    
    Orchestrates the complete workflow:
    1. Load templates
    2. Template selection
    3. Data collection (basic + conditional)
    4. Template customization
    5. Summary display and confirmation
    6. File saving
    """
    console.print(Panel.fit("📚 Generic PO Line Creator", style="bold blue"))
    
    # Load available templates
    templates = load_templates()
    if not templates:
        return
    
    # Main processing loop (allows creating multiple PO lines)
    while True:
        # === TEMPLATE SELECTION ===
        template_result = select_template(templates)
        if not template_result:
            console.print("👋 Goodbye!", style="bold cyan")
            break
        
        template_name, template = template_result
        console.print(f"\n✨ Selected template: {template_name}", style="bold green")
        
        # === DATA COLLECTION ===
        # Get basic order information
        user_input = get_user_input()
        if not user_input:
            continue
            
        # Get receiving note categories and conditional data
        receiving_categories, conditional_data = get_receiving_note_categories()
        
        # === PROCESSING ===
        # Apply user input to template
        po_data = customize_template(template, user_input, receiving_categories, conditional_data)
        
        # Generate descriptive filename
        filename = generate_filename(user_input)
        
        # === REVIEW AND CONFIRMATION ===
        # Display comprehensive summary
        display_summary(po_data, filename, receiving_categories, conditional_data)
        
        # Get user confirmation before saving
        confirm = questionary.confirm(f"Save this PO to {filename}?").ask()
        if confirm:
            if save_po_file(po_data, filename):
                console.print(f"✅ Successfully created: {filename}", style="bold green")
            else:
                console.print("❌ Failed to save file", style="bold red")
        else:
            console.print("❌ File not saved", style="yellow")
        
        # === CONTINUE OR EXIT ===
        another = questionary.confirm("Create another PO?").ask()
        if not another:
            console.print("👋 Goodbye!", style="bold cyan")
            break

if __name__ == "__main__":
    main()