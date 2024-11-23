# @title domain_name_gen.py
# Import necessary libraries
import requests
import xml.etree.ElementTree as ET
from google import generativeai as genai
from google.colab import userdata
from decimal import Decimal
import time

# MODULE: ENV VARIABLES
# Configuration constants
# User credentials need to be configured for the API


# MODULE: LLM
# Configure the Google Generative AI SDK
genai.configure(api_key=GOOGLE_API_KEY)

# Define common domain extensions as a variable
web_extension = ['.com']

# Create the Gemini model instance with parameter tuning options
model = genai.GenerativeModel("gemini-1.5-flash")

# Set to store all previously generated domain names
generated_domains_memory = set()

# Function to generate domain names using Generative AI
def generate_domain_names(topic_description, prompt_batch_size, max_price):
    """
    Generate domain names based on a given topic description using Google Generative AI.
    Args:
        topic_description (str): Description of the domain.
        prompt_batch_size (int): Number of domain names to generate.
        max_price (Decimal): Maximum acceptable price for domain registration.
    Returns:
        list: List of generated domain names.
    """
    # Create a prompt template to ensure consistency in generated output
    prompt_template = """
    Please generate exactly {batch_size} creative and short domain names related to the topic: "{topic}".
    Use only common extensions like {extensions} that usually cost less than ${price}.
    Each domain should be unique, memorable, and concise. Provide one domain per line, formatted exactly as follows: "domainname.com".
    Ensure that there are {batch_size} domain names generated without any deviation.
    """
    # Fill the prompt with the given parameters
    prompt = prompt_template.format(
        batch_size=prompt_batch_size,
        topic=topic_description,
        extensions=', '.join(web_extension),
        price=max_price
    )

    domain_names = []
    attempts = 0
    max_attempts = 3  # Limit the number of retries to avoid infinite loops
    while len(domain_names) < prompt_batch_size and attempts < max_attempts:
        try:
            # Generate content using the configured generative AI model
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    candidate_count=1,  # Generate only one candidate per request
                    stop_sequences=["x"],  # Stop sequence placeholder (can be updated as required)
                    max_output_tokens=8000,  # Increase to allow more tokens in response
                    temperature=0.5,  # Decrease temperature to reduce variability
                ),
            )
            generated_text = response.text
            lines = generated_text.strip().split('\n')

            # Extract valid domain names from the response, and avoid generating names that already exist in memory
            for line in lines:
                line = line.strip().lstrip('0123456789.- ').strip()  # Clean up the generated line
                if any(ext in line.lower() for ext in web_extension) and line.lower() not in generated_domains_memory:
                    domain_names.append(line.lower())

            # Ensure the number of generated domains matches the prompt batch size
            if len(domain_names) < prompt_batch_size:
                print(f"Warning: Only {len(domain_names)} domain names generated out of requested {prompt_batch_size}. Retrying...")
                attempts += 1
                prompt_batch_size -= len(domain_names)  # Adjust the batch size for the next attempt
        except Exception as e:
            # Handle exceptions and return an empty list in case of an error
            print(f"Error during domain generation: {str(e)}")
            attempts += 1

    return domain_names[:prompt_batch_size]  # Return only the requested number of domain names

# MODULE: DATA CONFIRMATION
# Function to confirm the validity of generated domain names
def confirm_generated_domains(domain_names):
    """
    Confirm that the generated domain names are valid and match the expected format.
    Args:
        domain_names (list): List of generated domain names.
    Returns:
        list: List of confirmed domain names.
    """
    confirmed_domains = []
    for domain in domain_names:
        if any(ext in domain for ext in web_extension):
            confirmed_domains.append(domain)
    return confirmed_domains

# MODULE: API NAMECHEAP
# Function to get domain prices using Namecheap API
def get_domain_prices(domains):
    """
    Check domain prices using Namecheap API.
    Args:
        domains (list): List of domain names to check.
    Returns:
        dict: A dictionary with domain names as keys and their prices as values.
    """
    base_url = 'https://api.sandbox.namecheap.com/xml.response'
    params = {
        'ApiUser': API_USER,
        'ApiKey': API_KEY,
        'UserName': USER_NAME,
        'ClientIp': CLIENT_IP,
        'Command': 'namecheap.domains.getpricing',
        'ProductType': 'DOMAIN'
    }

    try:
        # Make a request to the Namecheap API to get pricing details
        response = requests.get(base_url, params=params)
        response.raise_for_status()  # Add error check for HTTP request issues
        root = ET.fromstring(response.content)

        # Define namespace used in the XML response
        ns = {'nc': 'http://api.namecheap.com/xml.response'}

        domain_prices = {}
        for domain in domains:
            tld = domain.split('.')[-1]

            # Find the TLD pricing element in the response XML
            for product in root.findall('.//nc:ProductType/nc:ProductCategory/nc:Product', ns):
                if product.get('name').lower() == f'.{tld}'.lower():
                    # Get price for 1 year registration if available
                    price_element = product.find('.//nc:Price[@Duration="1"]', ns)
                    if price_element is not None:
                        price = Decimal(price_element.get('Price', '0'))
                        domain_prices[domain] = price
                        break

            # If price wasn't found, set a high default price to indicate unavailability
            if domain not in domain_prices:
                domain_prices[domain] = Decimal('999999')

        return domain_prices
    except requests.exceptions.RequestException as e:
        # Handle HTTP request exceptions and return high price for all domains in case of error
        print(f"Error getting prices: {str(e)}")
        return {domain: Decimal('999999') for domain in domains}
    except ET.ParseError as e:
        # Handle XML parsing exceptions
        print(f"Error parsing XML response: {str(e)}")
        return {domain: Decimal('999999') for domain in domains}

# Function to check domain availability using Namecheap API
def check_domain_availability(domain):
    """
    Check domain availability using Namecheap API for a single domain.
    Args:
        domain (str): Domain name to check.
    Returns:
        bool: True if domain is available, False otherwise.
    """
    base_url = 'https://api.sandbox.namecheap.com/xml.response'
    params = {
        'ApiUser': API_USER,
        'ApiKey': API_KEY,
        'UserName': USER_NAME,
        'ClientIp': CLIENT_IP,
        'Command': 'namecheap.domains.check',
        'DomainList': domain
    }

    try:
        # Make a request to the Namecheap API to check domain availability
        response = requests.get(base_url, params=params)
        response.raise_for_status()  # Add error check for HTTP request issues
        root = ET.fromstring(response.content)
        ns = {'nc': 'http://api.namecheap.com/xml.response'}

        # Parse the response to determine if the domain is available
        domain_check_result = root.find('.//nc:DomainCheckResult', ns)
        if domain_check_result is not None:
            available = domain_check_result.get('Available', '').lower() == 'true'
            return available
        return False
    except requests.exceptions.RequestException as e:
        # Handle HTTP request exceptions and return False if unable to check availability
        print(f"Error checking availability: {str(e)}")
        return False
    except ET.ParseError as e:
        # Handle XML parsing exceptions
        print(f"Error parsing XML response: {str(e)}")
        return False

# MODULE: ORCHESTRATION
# Orchestrator function to get available domains within budget
# STEP 1: Generate domain names using LLM
# STEP 2: Confirm domain format using DATA CONFIRMATION
# STEP 3: Get domain prices using API NAMECHEAP
# STEP 4: Check domain availability using API NAMECHEAP
def find_available_domains(topic_description, max_price):
    """
    Find available domains based on topic description, price, and availability.
    Args:
        topic_description (str): Description of the domain.
        max_price (Decimal): Maximum acceptable price for domain registration.
    Returns:
        list: List of available domain names within the budget.
    """
    available_domains = []
    attempt = 0
    max_attempts = 5  # Maximum number of attempts to generate domains and find available ones

    while not available_domains and attempt < max_attempts:
        attempt += 1
        # STEP 1: Generate 200 domain names using the generative AI model (LLM)
        domain_names = generate_domain_names(topic_description, prompt_batch_size=200, max_price=max_price)

        # STEP 2: Confirm that the generated domains are in the correct format (DATA CONFIRMATION)
        confirmed_domains = confirm_generated_domains(domain_names)

        # Filter out previously generated domain names
        new_domain_names = [domain for domain in confirmed_domains if domain not in generated_domains_memory]

        # Add newly generated names to the memory to avoid repetition
        generated_domains_memory.update(new_domain_names)

        if not new_domain_names:
            print("No new domain names generated. Generating new batch...")
            continue

        # STEP 3: Get the prices for the entire batch of new domain names (API NAMECHEAP)
        domain_prices = get_domain_prices(new_domain_names)

        # STEP 4: Process each domain to check availability with a delay of 2 seconds per request (API NAMECHEAP)
        for domain in new_domain_names:
            # Get the price of the domain
            price = domain_prices.get(domain, Decimal('999999'))

            # Check if the domain is within the budget and available
            if price <= max_price:
                is_available = check_domain_availability(domain)
                time.sleep(2)  # Respect Namecheap API limit of 30 requests per minute

                if is_available:
                    available_domains.append(domain)
                    print(f"{domain} is available for ${price:.2f}.")
                else:
                    print(f"{domain} is not available.")
            else:
                print(f"{domain} is not within the price range (Price: ${price:.2f}).")

        if not available_domains:
            print(f"\nNo available domains found within your budget in attempt {attempt}. Generating new batch...")

    return available_domains

# MODULE: MAIN
# Get user input
topic_description = "AI and quantum computing"  # Placeholder for user input
max_price = Decimal(20)  # Placeholder for user input, ensure max_price is Decimal

# Find available domains
available_domains = find_available_domains(topic_description, max_price)

# Display available domains
if available_domains:
    print("\nAvailable domains within your budget:")
    for domain in available_domains:
        # Retrieve the price again for displaying purposes
        price = get_domain_prices([domain])[domain]
        print(f"{domain} - ${price:.2f}")
else:
    print("\nNo available domains found within your budget after maximum attempts.")
