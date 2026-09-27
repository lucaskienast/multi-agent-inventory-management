import pandas as pd
import numpy as np
import os
import time
import dotenv
import ast
import difflib
import re
from sqlalchemy.sql import text
from datetime import datetime, timedelta
from typing import Dict, List, Union
from sqlalchemy import create_engine, Engine
from smolagents import OpenAIServerModel, ToolCallingAgent, tool

# Create an SQLite database
db_engine = create_engine("sqlite:///munder_difflin.db")

# List containing the different kinds of papers 
paper_supplies = [
    # Paper Types (priced per sheet unless specified)
    {"item_name": "A4 paper",                         "category": "paper",        "unit_price": 0.05},
    {"item_name": "Letter-sized paper",              "category": "paper",        "unit_price": 0.06},
    {"item_name": "Cardstock",                        "category": "paper",        "unit_price": 0.15},
    {"item_name": "Colored paper",                    "category": "paper",        "unit_price": 0.10},
    {"item_name": "Glossy paper",                     "category": "paper",        "unit_price": 0.20},
    {"item_name": "Matte paper",                      "category": "paper",        "unit_price": 0.18},
    {"item_name": "Recycled paper",                   "category": "paper",        "unit_price": 0.08},
    {"item_name": "Eco-friendly paper",               "category": "paper",        "unit_price": 0.12},
    {"item_name": "Poster paper",                     "category": "paper",        "unit_price": 0.25},
    {"item_name": "Banner paper",                     "category": "paper",        "unit_price": 0.30},
    {"item_name": "Kraft paper",                      "category": "paper",        "unit_price": 0.10},
    {"item_name": "Construction paper",               "category": "paper",        "unit_price": 0.07},
    {"item_name": "Wrapping paper",                   "category": "paper",        "unit_price": 0.15},
    {"item_name": "Glitter paper",                    "category": "paper",        "unit_price": 0.22},
    {"item_name": "Decorative paper",                 "category": "paper",        "unit_price": 0.18},
    {"item_name": "Letterhead paper",                 "category": "paper",        "unit_price": 0.12},
    {"item_name": "Legal-size paper",                 "category": "paper",        "unit_price": 0.08},
    {"item_name": "Crepe paper",                      "category": "paper",        "unit_price": 0.05},
    {"item_name": "Photo paper",                      "category": "paper",        "unit_price": 0.25},
    {"item_name": "Uncoated paper",                   "category": "paper",        "unit_price": 0.06},
    {"item_name": "Butcher paper",                    "category": "paper",        "unit_price": 0.10},
    {"item_name": "Heavyweight paper",                "category": "paper",        "unit_price": 0.20},
    {"item_name": "Standard copy paper",              "category": "paper",        "unit_price": 0.04},
    {"item_name": "Bright-colored paper",             "category": "paper",        "unit_price": 0.12},
    {"item_name": "Patterned paper",                  "category": "paper",        "unit_price": 0.15},

    # Product Types (priced per unit)
    {"item_name": "Paper plates",                     "category": "product",      "unit_price": 0.10},  # per plate
    {"item_name": "Paper cups",                       "category": "product",      "unit_price": 0.08},  # per cup
    {"item_name": "Paper napkins",                    "category": "product",      "unit_price": 0.02},  # per napkin
    {"item_name": "Disposable cups",                  "category": "product",      "unit_price": 0.10},  # per cup
    {"item_name": "Table covers",                     "category": "product",      "unit_price": 1.50},  # per cover
    {"item_name": "Envelopes",                        "category": "product",      "unit_price": 0.05},  # per envelope
    {"item_name": "Sticky notes",                     "category": "product",      "unit_price": 0.03},  # per sheet
    {"item_name": "Notepads",                         "category": "product",      "unit_price": 2.00},  # per pad
    {"item_name": "Invitation cards",                 "category": "product",      "unit_price": 0.50},  # per card
    {"item_name": "Flyers",                           "category": "product",      "unit_price": 0.15},  # per flyer
    {"item_name": "Party streamers",                  "category": "product",      "unit_price": 0.05},  # per roll
    {"item_name": "Decorative adhesive tape (washi tape)", "category": "product", "unit_price": 0.20},  # per roll
    {"item_name": "Paper party bags",                 "category": "product",      "unit_price": 0.25},  # per bag
    {"item_name": "Name tags with lanyards",          "category": "product",      "unit_price": 0.75},  # per tag
    {"item_name": "Presentation folders",             "category": "product",      "unit_price": 0.50},  # per folder

    # Large-format items (priced per unit)
    {"item_name": "Large poster paper (24x36 inches)", "category": "large_format", "unit_price": 1.00},
    {"item_name": "Rolls of banner paper (36-inch width)", "category": "large_format", "unit_price": 2.50},

    # Specialty papers
    {"item_name": "100 lb cover stock",               "category": "specialty",    "unit_price": 0.50},
    {"item_name": "80 lb text paper",                 "category": "specialty",    "unit_price": 0.40},
    {"item_name": "250 gsm cardstock",                "category": "specialty",    "unit_price": 0.30},
    {"item_name": "220 gsm poster paper",             "category": "specialty",    "unit_price": 0.35},
]

# Given below are some utility functions you can use to implement your multi-agent system

def generate_sample_inventory(paper_supplies: list, coverage: float = 0.4, seed: int = 137) -> pd.DataFrame:
    """
    Generate inventory for exactly a specified percentage of items from the full paper supply list.

    This function randomly selects exactly `coverage` × N items from the `paper_supplies` list,
    and assigns each selected item:
    - a random stock quantity between 200 and 800,
    - a minimum stock level between 50 and 150.

    The random seed ensures reproducibility of selection and stock levels.

    Args:
        paper_supplies (list): A list of dictionaries, each representing a paper item with
                               keys 'item_name', 'category', and 'unit_price'.
        coverage (float, optional): Fraction of items to include in the inventory (default is 0.4, or 40%).
        seed (int, optional): Random seed for reproducibility (default is 137).

    Returns:
        pd.DataFrame: A DataFrame with the selected items and assigned inventory values, including:
                      - item_name
                      - category
                      - unit_price
                      - current_stock
                      - min_stock_level
    """
    # Ensure reproducible random output
    np.random.seed(seed)

    # Calculate number of items to include based on coverage
    num_items = int(len(paper_supplies) * coverage)

    # Randomly select item indices without replacement
    selected_indices = np.random.choice(
        range(len(paper_supplies)),
        size=num_items,
        replace=False
    )

    # Extract selected items from paper_supplies list
    selected_items = [paper_supplies[i] for i in selected_indices]

    # Construct inventory records
    inventory = []
    for item in selected_items:
        inventory.append({
            "item_name": item["item_name"],
            "category": item["category"],
            "unit_price": item["unit_price"],
            "current_stock": np.random.randint(200, 800),  # Realistic stock range
            "min_stock_level": np.random.randint(50, 150)  # Reasonable threshold for reordering
        })

    # Return inventory as a pandas DataFrame
    return pd.DataFrame(inventory)

def init_database(db_engine: Engine, seed: int = 137) -> Engine:    
    """
    Set up the Munder Difflin database with all required tables and initial records.

    This function performs the following tasks:
    - Creates the 'transactions' table for logging stock orders and sales
    - Loads customer inquiries from 'quote_requests.csv' into a 'quote_requests' table
    - Loads previous quotes from 'quotes.csv' into a 'quotes' table, extracting useful metadata
    - Generates a random subset of paper inventory using `generate_sample_inventory`
    - Inserts initial financial records including available cash and starting stock levels

    Args:
        db_engine (Engine): A SQLAlchemy engine connected to the SQLite database.
        seed (int, optional): A random seed used to control reproducibility of inventory stock levels.
                              Default is 137.

    Returns:
        Engine: The same SQLAlchemy engine, after initializing all necessary tables and records.

    Raises:
        Exception: If an error occurs during setup, the exception is printed and raised.
    """
    try:
        # ----------------------------
        # 1. Create an empty 'transactions' table schema
        # ----------------------------
        transactions_schema = pd.DataFrame({
            "id": [],
            "item_name": [],
            "transaction_type": [],  # 'stock_orders' or 'sales'
            "units": [],             # Quantity involved
            "price": [],             # Total price for the transaction
            "transaction_date": [],  # ISO-formatted date
        })
        transactions_schema.to_sql("transactions", db_engine, if_exists="replace", index=False)

        # Set a consistent starting date
        initial_date = datetime(2025, 1, 1).isoformat()

        # ----------------------------
        # 2. Load and initialize 'quote_requests' table
        # ----------------------------
        quote_requests_df = pd.read_csv("quote_requests.csv")
        quote_requests_df["id"] = range(1, len(quote_requests_df) + 1)
        quote_requests_df.to_sql("quote_requests", db_engine, if_exists="replace", index=False)

        # ----------------------------
        # 3. Load and transform 'quotes' table
        # ----------------------------
        quotes_df = pd.read_csv("quotes.csv")
        quotes_df["request_id"] = range(1, len(quotes_df) + 1)
        quotes_df["order_date"] = initial_date

        # Unpack metadata fields (job_type, order_size, event_type) if present
        if "request_metadata" in quotes_df.columns:
            quotes_df["request_metadata"] = quotes_df["request_metadata"].apply(
                lambda x: ast.literal_eval(x) if isinstance(x, str) else x
            )
            quotes_df["job_type"] = quotes_df["request_metadata"].apply(lambda x: x.get("job_type", ""))
            quotes_df["order_size"] = quotes_df["request_metadata"].apply(lambda x: x.get("order_size", ""))
            quotes_df["event_type"] = quotes_df["request_metadata"].apply(lambda x: x.get("event_type", ""))

        # Retain only relevant columns
        quotes_df = quotes_df[[
            "request_id",
            "total_amount",
            "quote_explanation",
            "order_date",
            "job_type",
            "order_size",
            "event_type"
        ]]
        quotes_df.to_sql("quotes", db_engine, if_exists="replace", index=False)

        # ----------------------------
        # 4. Generate inventory and seed stock
        # ----------------------------
        inventory_df = generate_sample_inventory(paper_supplies, seed=seed)

        # Seed initial transactions
        initial_transactions = []

        # Add a starting cash balance via a dummy sales transaction
        initial_transactions.append({
            "item_name": None,
            "transaction_type": "sales",
            "units": None,
            "price": 50000.0,
            "transaction_date": initial_date,
        })

        # Add one stock order transaction per inventory item
        for _, item in inventory_df.iterrows():
            initial_transactions.append({
                "item_name": item["item_name"],
                "transaction_type": "stock_orders",
                "units": item["current_stock"],
                "price": item["current_stock"] * item["unit_price"],
                "transaction_date": initial_date,
            })

        # Commit transactions to database
        pd.DataFrame(initial_transactions).to_sql("transactions", db_engine, if_exists="append", index=False)

        # Save the inventory reference table
        inventory_df.to_sql("inventory", db_engine, if_exists="replace", index=False)

        return db_engine

    except Exception as e:
        print(f"Error initializing database: {e}")
        raise

def create_transaction(
    item_name: str,
    transaction_type: str,
    quantity: int,
    price: float,
    date: Union[str, datetime],
) -> int:
    """
    This function records a transaction of type 'stock_orders' or 'sales' with a specified
    item name, quantity, total price, and transaction date into the 'transactions' table of the database.

    Args:
        item_name (str): The name of the item involved in the transaction.
        transaction_type (str): Either 'stock_orders' or 'sales'.
        quantity (int): Number of units involved in the transaction.
        price (float): Total price of the transaction.
        date (str or datetime): Date of the transaction in ISO 8601 format.

    Returns:
        int: The ID of the newly inserted transaction.

    Raises:
        ValueError: If `transaction_type` is not 'stock_orders' or 'sales'.
        Exception: For other database or execution errors.
    """
    try:
        # Convert datetime to ISO string if necessary
        date_str = date.isoformat() if isinstance(date, datetime) else date

        # Validate transaction type
        if transaction_type not in {"stock_orders", "sales"}:
            raise ValueError("Transaction type must be 'stock_orders' or 'sales'")

        # Prepare transaction record as a single-row DataFrame
        transaction = pd.DataFrame([{
            "item_name": item_name,
            "transaction_type": transaction_type,
            "units": quantity,
            "price": price,
            "transaction_date": date_str,
        }])

        # Insert the record into the database
        transaction.to_sql("transactions", db_engine, if_exists="append", index=False)

        # Fetch and return the ID of the inserted row
        result = pd.read_sql("SELECT last_insert_rowid() as id", db_engine)
        return int(result.iloc[0]["id"])

    except Exception as e:
        print(f"Error creating transaction: {e}")
        raise

def get_all_inventory(as_of_date: str) -> Dict[str, int]:
    """
    Retrieve a snapshot of available inventory as of a specific date.

    This function calculates the net quantity of each item by summing 
    all stock orders and subtracting all sales up to and including the given date.

    Only items with positive stock are included in the result.

    Args:
        as_of_date (str): ISO-formatted date string (YYYY-MM-DD) representing the inventory cutoff.

    Returns:
        Dict[str, int]: A dictionary mapping item names to their current stock levels.
    """
    # SQL query to compute stock levels per item as of the given date
    query = """
        SELECT
            item_name,
            SUM(CASE
                WHEN transaction_type = 'stock_orders' THEN units
                WHEN transaction_type = 'sales' THEN -units
                ELSE 0
            END) as stock
        FROM transactions
        WHERE item_name IS NOT NULL
        AND transaction_date <= :as_of_date
        GROUP BY item_name
        HAVING stock > 0
    """

    # Execute the query with the date parameter
    result = pd.read_sql(query, db_engine, params={"as_of_date": as_of_date})

    # Convert the result into a dictionary {item_name: stock}
    return dict(zip(result["item_name"], result["stock"]))

def get_stock_level(item_name: str, as_of_date: Union[str, datetime]) -> pd.DataFrame:
    """
    Retrieve the stock level of a specific item as of a given date.

    This function calculates the net stock by summing all 'stock_orders' and 
    subtracting all 'sales' transactions for the specified item up to the given date.

    Args:
        item_name (str): The name of the item to look up.
        as_of_date (str or datetime): The cutoff date (inclusive) for calculating stock.

    Returns:
        pd.DataFrame: A single-row DataFrame with columns 'item_name' and 'current_stock'.
    """
    # Convert date to ISO string format if it's a datetime object
    if isinstance(as_of_date, datetime):
        as_of_date = as_of_date.isoformat()

    # SQL query to compute net stock level for the item
    stock_query = """
        SELECT
            item_name,
            COALESCE(SUM(CASE
                WHEN transaction_type = 'stock_orders' THEN units
                WHEN transaction_type = 'sales' THEN -units
                ELSE 0
            END), 0) AS current_stock
        FROM transactions
        WHERE item_name = :item_name
        AND transaction_date <= :as_of_date
    """

    # Execute query and return result as a DataFrame
    return pd.read_sql(
        stock_query,
        db_engine,
        params={"item_name": item_name, "as_of_date": as_of_date},
    )

def get_supplier_delivery_date(input_date_str: str, quantity: int) -> str:
    """
    Estimate the supplier delivery date based on the requested order quantity and a starting date.

    Delivery lead time increases with order size:
        - ≤10 units: same day
        - 11–100 units: 1 day
        - 101–1000 units: 4 days
        - >1000 units: 7 days

    Args:
        input_date_str (str): The starting date in ISO format (YYYY-MM-DD).
        quantity (int): The number of units in the order.

    Returns:
        str: Estimated delivery date in ISO format (YYYY-MM-DD).
    """
    # Debug log (comment out in production if needed)
    print(f"FUNC (get_supplier_delivery_date): Calculating for qty {quantity} from date string '{input_date_str}'")

    # Attempt to parse the input date
    try:
        input_date_dt = datetime.fromisoformat(input_date_str.split("T")[0])
    except (ValueError, TypeError):
        # Fallback to current date on format error
        print(f"WARN (get_supplier_delivery_date): Invalid date format '{input_date_str}', using today as base.")
        input_date_dt = datetime.now()

    # Determine delivery delay based on quantity
    if quantity <= 10:
        days = 0
    elif quantity <= 100:
        days = 1
    elif quantity <= 1000:
        days = 4
    else:
        days = 7

    # Add delivery days to the starting date
    delivery_date_dt = input_date_dt + timedelta(days=days)

    # Return formatted delivery date
    return delivery_date_dt.strftime("%Y-%m-%d")

def get_cash_balance(as_of_date: Union[str, datetime]) -> float:
    """
    Calculate the current cash balance as of a specified date.

    The balance is computed by subtracting total stock purchase costs ('stock_orders')
    from total revenue ('sales') recorded in the transactions table up to the given date.

    Args:
        as_of_date (str or datetime): The cutoff date (inclusive) in ISO format or as a datetime object.

    Returns:
        float: Net cash balance as of the given date. Returns 0.0 if no transactions exist or an error occurs.
    """
    try:
        # Convert date to ISO format if it's a datetime object
        if isinstance(as_of_date, datetime):
            as_of_date = as_of_date.isoformat()

        # Query all transactions on or before the specified date
        transactions = pd.read_sql(
            "SELECT * FROM transactions WHERE transaction_date <= :as_of_date",
            db_engine,
            params={"as_of_date": as_of_date},
        )

        # Compute the difference between sales and stock purchases
        if not transactions.empty:
            total_sales = transactions.loc[transactions["transaction_type"] == "sales", "price"].sum()
            total_purchases = transactions.loc[transactions["transaction_type"] == "stock_orders", "price"].sum()
            return float(total_sales - total_purchases)

        return 0.0

    except Exception as e:
        print(f"Error getting cash balance: {e}")
        return 0.0


def generate_financial_report(as_of_date: Union[str, datetime]) -> Dict:
    """
    Generate a complete financial report for the company as of a specific date.

    This includes:
    - Cash balance
    - Inventory valuation
    - Combined asset total
    - Itemized inventory breakdown
    - Top 5 best-selling products

    Args:
        as_of_date (str or datetime): The date (inclusive) for which to generate the report.

    Returns:
        Dict: A dictionary containing the financial report fields:
            - 'as_of_date': The date of the report
            - 'cash_balance': Total cash available
            - 'inventory_value': Total value of inventory
            - 'total_assets': Combined cash and inventory value
            - 'inventory_summary': List of items with stock and valuation details
            - 'top_selling_products': List of top 5 products by revenue
    """
    # Normalize date input
    if isinstance(as_of_date, datetime):
        as_of_date = as_of_date.isoformat()

    # Get current cash balance
    cash = get_cash_balance(as_of_date)

    # Get current inventory snapshot
    inventory_df = pd.read_sql("SELECT * FROM inventory", db_engine)
    inventory_value = 0.0
    inventory_summary = []

    # Compute total inventory value and summary by item
    for _, item in inventory_df.iterrows():
        stock_info = get_stock_level(item["item_name"], as_of_date)
        stock = stock_info["current_stock"].iloc[0]
        item_value = stock * item["unit_price"]
        inventory_value += item_value

        inventory_summary.append({
            "item_name": item["item_name"],
            "stock": stock,
            "unit_price": item["unit_price"],
            "value": item_value,
        })

    # Identify top-selling products by revenue
    top_sales_query = """
        SELECT item_name, SUM(units) as total_units, SUM(price) as total_revenue
        FROM transactions
        WHERE transaction_type = 'sales' AND transaction_date <= :date
        GROUP BY item_name
        ORDER BY total_revenue DESC
        LIMIT 5
    """
    top_sales = pd.read_sql(top_sales_query, db_engine, params={"date": as_of_date})
    top_selling_products = top_sales.to_dict(orient="records")

    return {
        "as_of_date": as_of_date,
        "cash_balance": cash,
        "inventory_value": inventory_value,
        "total_assets": cash + inventory_value,
        "inventory_summary": inventory_summary,
        "top_selling_products": top_selling_products,
    }


def search_quote_history(search_terms: List[str], limit: int = 5) -> List[Dict]:
    """
    Retrieve a list of historical quotes that match any of the provided search terms.

    The function searches both the original customer request (from `quote_requests`) and
    the explanation for the quote (from `quotes`) for each keyword. Results are sorted by
    most recent order date and limited by the `limit` parameter.

    Args:
        search_terms (List[str]): List of terms to match against customer requests and explanations.
        limit (int, optional): Maximum number of quote records to return. Default is 5.

    Returns:
        List[Dict]: A list of matching quotes, each represented as a dictionary with fields:
            - original_request
            - total_amount
            - quote_explanation
            - job_type
            - order_size
            - event_type
            - order_date
    """
    conditions = []
    params = {}

    # Build SQL WHERE clause using LIKE filters for each search term
    for i, term in enumerate(search_terms):
        param_name = f"term_{i}"
        conditions.append(
            f"(LOWER(qr.response) LIKE :{param_name} OR "
            f"LOWER(q.quote_explanation) LIKE :{param_name})"
        )
        params[param_name] = f"%{term.lower()}%"

    # Combine conditions; fallback to always-true if no terms provided
    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # Final SQL query to join quotes with quote_requests
    query = f"""
        SELECT
            qr.response AS original_request,
            q.total_amount,
            q.quote_explanation,
            q.job_type,
            q.order_size,
            q.event_type,
            q.order_date
        FROM quotes q
        JOIN quote_requests qr ON q.request_id = qr.id
        WHERE {where_clause}
        ORDER BY q.order_date DESC
        LIMIT {limit}
    """

    # Execute parameterized query
    with db_engine.connect() as conn:
        result = conn.execute(text(query), params)
        return [dict(row._mapping) for row in result]

########################
########################
########################
# YOUR MULTI AGENT STARTS HERE
########################
########################
########################



# ---------------------------------------------------------------------------
# Environment and model
# ---------------------------------------------------------------------------

dotenv.load_dotenv()

VOCAREUM_API_BASE = "https://openai.vocareum.com/v1"
MODEL_ID = os.getenv("AGENT_MODEL_ID", "gpt-4o-mini")
# smolagents log level: 0 = silent, 1 = steps and tool calls, 2 = debug
AGENT_VERBOSITY = int(os.getenv("AGENT_VERBOSITY", "1"))


def build_model() -> OpenAIServerModel:
    """Create the chat model.

    Uses the Udacity/Vocareum proxy when UDACITY_OPENAI_API_KEY is set (the course workspace);
    otherwise falls back to a personal OPENAI_API_KEY against OpenAI's own endpoint.
    """
    udacity_key = os.getenv("UDACITY_OPENAI_API_KEY")
    if udacity_key:
        return OpenAIServerModel(model_id=MODEL_ID, api_base=VOCAREUM_API_BASE, api_key=udacity_key)
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        return OpenAIServerModel(model_id=MODEL_ID, api_key=openai_key)  # default OpenAI endpoint
    raise RuntimeError("Set UDACITY_OPENAI_API_KEY (Udacity proxy) or OPENAI_API_KEY in project/.env")


# ---------------------------------------------------------------------------
# Business constants and shared in-process state
# ---------------------------------------------------------------------------

# Full product catalog keyed by exact item name (the DB only stocks a subset of it)
CATALOG: Dict[str, Dict] = {item["item_name"]: item for item in paper_supplies}

# Used when a customer gives no delivery deadline
DEFAULT_DELIVERY_WINDOW_DAYS = 14

# The catalog unit_price is the customer list price (as used in the historical quotes). The
# supplier sells to us at a wholesale discount; without it every discounted sale of restocked
# goods would lose money. Assumption: wholesale cost = 70% of list price (30% gross margin).
SUPPLIER_COST_RATE = 0.70

# Bulk discount by total units in the quote: (minimum units, discount rate), checked top-down
BULK_DISCOUNT_TIERS = [(10_000, 0.15), (2_000, 0.10), (500, 0.05), (0, 0.0)]

# Quotes issued by the quoting agent, looked up by fulfill_order so that the sales agent books
# exactly the quoted lines and prices (the LLM only ever passes the quote_id around).
QUOTES: Dict[str, Dict] = {}

# (item_name, request_date) -> date on which restocked goods reach us, i.e. the earliest date the
# customer can receive that item. Written by restock_item, read by fulfill_order.
CUSTOMER_AVAILABILITY_DATES: Dict[tuple, str] = {}


def reset_session_state() -> None:
    """Clear in-process state; call together with init_database() so both start fresh."""
    QUOTES.clear()
    CUSTOMER_AVAILABILITY_DATES.clear()


# ---------------------------------------------------------------------------
# Internal helpers used by the tools (not exposed to the agents)
# ---------------------------------------------------------------------------

def _to_iso_date(value: Union[str, datetime]) -> str:
    """Normalise a date to 'YYYY-MM-DD'.

    Transactions must never carry a time component: the starter queries compare dates as text,
    so '2025-04-05T10:00:00' would be invisible to a query 'as of 2025-04-05'.
    """
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    date_part = str(value).strip().split("T")[0].split(" ")[0]
    return datetime.fromisoformat(date_part).strftime("%Y-%m-%d")


def _stock_on(item_name: str, as_of_date: str) -> int:
    """Net units of an item in stock as of a date (0 if it was never stocked)."""
    stock_df = get_stock_level(item_name, as_of_date)
    return int(stock_df["current_stock"].iloc[0]) if not stock_df.empty else 0


def _min_stock_levels() -> Dict[str, int]:
    """Reorder thresholds from the inventory table (only the initially stocked items have one)."""
    levels = pd.read_sql("SELECT item_name, min_stock_level FROM inventory", db_engine)
    return dict(zip(levels["item_name"], levels["min_stock_level"].astype(int)))


def _unknown_item_error(item_name: str) -> Dict:
    """Uniform error for names that are not exact catalog names, with suggestions."""
    suggestions = difflib.get_close_matches(item_name, list(CATALOG), n=3, cutoff=0.5)
    return {
        "error": f"'{item_name}' is not an exact catalog item name.",
        "did_you_mean": suggestions,
    }


def _log(message: str) -> None:
    """One-line trace of tool activity so each test run can be followed in the console."""
    print(f"    [tool] {message}")


# Keyword rules mapping free-text customer descriptions to catalog items. Checked in order:
# specific products first, then paper types, then generic colour/size words, so that e.g.
# "colorful poster paper" -> Poster paper and "kraft paper envelopes" -> Envelopes.
_CATALOG_MATCH_RULES = [
    (r"washi|adhesive tape", "Decorative adhesive tape (washi tape)"),
    (r"streamer", "Party streamers"),
    (r"napkin", "Paper napkins"),
    (r"plate", "Paper plates"),
    (r"disposable cup", "Disposable cups"),
    (r"\bcups?\b", "Paper cups"),
    (r"table ?cover|tablecloth", "Table covers"),
    (r"envelope", "Envelopes"),
    (r"sticky", "Sticky notes"),
    (r"note ?pad", "Notepads"),
    (r"invitation", "Invitation cards"),
    (r"flyer|leaflet", "Flyers"),
    (r"name tag|lanyard", "Name tags with lanyards"),
    (r"party bag", "Paper party bags"),
    (r"folder", "Presentation folders"),
    (r"poster ?board|24 ?(x|by) ?36", "Large poster paper (24x36 inches)"),
    (r"banner.*roll|roll.*banner|36.?inch", "Rolls of banner paper (36-inch width)"),
    (r"100 ?lb|cover ?stock", "100 lb cover stock"),
    (r"80 ?lb|text paper", "80 lb text paper"),
    (r"250 ?gsm", "250 gsm cardstock"),
    (r"220 ?gsm", "220 gsm poster paper"),
    (r"card ?stock", "Cardstock"),
    (r"poster", "Poster paper"),
    (r"banner", "Banner paper"),
    (r"letterhead", "Letterhead paper"),
    (r"legal", "Legal-size paper"),
    (r"gloss", "Glossy paper"),
    (r"matte", "Matte paper"),
    (r"glitter", "Glitter paper"),
    (r"kraft", "Kraft paper"),
    (r"butcher", "Butcher paper"),
    (r"crepe", "Crepe paper"),
    (r"wrapping|gift ?wrap", "Wrapping paper"),
    (r"construction", "Construction paper"),
    (r"heavy ?weight", "Heavyweight paper"),
    (r"uncoated", "Uncoated paper"),
    (r"patterned", "Patterned paper"),
    (r"recycled", "Recycled paper"),
    (r"\beco", "Eco-friendly paper"),
    (r"decorative", "Decorative paper"),
    (r"bright", "Bright-colored paper"),
    (r"colou?r", "Colored paper"),
    (r"printer|printing|copy|copier|multi-?purpose", "Standard copy paper"),
    (r"photo", "Photo paper"),
    (r"letter|8\.5", "Letter-sized paper"),
    (r"\ba4\b", "A4 paper"),
    # plain paper in a size we do not carry (typed paper in any size was matched above)
    (r"\ba[0-35-9]\b", None),
]


def _match_description(description: str) -> Dict:
    """Map one free-text item description to an exact catalog name (or None)."""
    lowered = description.lower().strip()
    exact = {name.lower(): name for name in CATALOG}
    if lowered in exact:
        return {"description": description, "match": exact[lowered], "method": "exact"}
    for pattern, catalog_name in _CATALOG_MATCH_RULES:
        if re.search(pattern, lowered):
            if catalog_name is None:
                return {"description": description, "match": None, "method": "keyword",
                        "reason": "paper size not carried (we stock A4, letter and legal size)"}
            return {"description": description, "match": catalog_name, "method": "keyword"}
    fuzzy = difflib.get_close_matches(lowered, list(exact), n=3, cutoff=0.6)
    if fuzzy and difflib.SequenceMatcher(None, lowered, fuzzy[0]).ratio() >= 0.8:
        return {"description": description, "match": exact[fuzzy[0]], "method": "fuzzy"}
    return {
        "description": description,
        "match": None,
        "method": "none",
        "closest_catalog_items": [exact[name] for name in fuzzy],
    }


# ---------------------------------------------------------------------------
# Tools for the orchestrator
# ---------------------------------------------------------------------------

@tool
def match_catalog_items(item_descriptions: list[str]) -> list[dict]:
    """Map the customer's own item descriptions to exact catalog item names.

    Always call this before delegating: the database only accepts exact catalog names.
    Items with match = null are products we do not sell (e.g. balloons, tickets, A3 paper).

    Args:
        item_descriptions: Item descriptions as written by the customer, without quantities,
            e.g. ["A4 glossy paper", "heavy cardstock (white)", "balloons"].
    """
    results = [_match_description(description) for description in item_descriptions]
    _log(f"match_catalog_items -> {[(r['description'], r['match']) for r in results]}")
    return results


# ---------------------------------------------------------------------------
# Tools for the inventory agent
# ---------------------------------------------------------------------------

@tool
def get_stock_level_tool(item_name: str, as_of_date: str) -> dict:
    """Get the current stock of one catalog item as of a date (wraps get_stock_level).

    Args:
        item_name: Exact catalog item name, e.g. "Glossy paper".
        as_of_date: Date in YYYY-MM-DD format (use the customer's request date).
    """
    if item_name not in CATALOG:
        return _unknown_item_error(item_name)
    as_of_date = _to_iso_date(as_of_date)
    stock = _stock_on(item_name, as_of_date)
    min_level = _min_stock_levels().get(item_name)
    _log(f"get_stock_level_tool({item_name}, {as_of_date}) -> {stock}")
    return {
        "item_name": item_name,
        "as_of_date": as_of_date,
        "current_stock": stock,
        "min_stock_level": min_level,
        "below_min_stock_level": min_level is not None and stock < min_level,
    }


@tool
def get_all_inventory_tool(as_of_date: str) -> dict:
    """List every item currently in stock and flag items below their minimum stock level
    (wraps get_all_inventory). Use it for general inventory questions and restock reviews.

    Args:
        as_of_date: Date in YYYY-MM-DD format.
    """
    as_of_date = _to_iso_date(as_of_date)
    in_stock = {name: int(units) for name, units in get_all_inventory(as_of_date).items()}
    min_levels = _min_stock_levels()
    low_stock = [
        {"item_name": name, "current_stock": in_stock.get(name, 0), "min_stock_level": level}
        for name, level in min_levels.items()
        if in_stock.get(name, 0) < level
    ]
    _log(f"get_all_inventory_tool({as_of_date}) -> {len(in_stock)} items, {len(low_stock)} low")
    return {"as_of_date": as_of_date, "items_in_stock": in_stock, "items_below_min_stock": low_stock}


@tool
def get_supplier_delivery_date_tool(order_date: str, quantity: int) -> dict:
    """Estimate when the supplier would deliver an order of a given size
    (wraps get_supplier_delivery_date). Lead time grows with quantity.

    Args:
        order_date: Date the supplier order is placed, YYYY-MM-DD.
        quantity: Number of units to order from the supplier.
    """
    order_date = _to_iso_date(order_date)
    delivery_date = get_supplier_delivery_date(order_date, int(quantity))
    return {"order_date": order_date, "quantity": int(quantity), "supplier_delivery_date": delivery_date}


@tool
def get_cash_balance_tool(as_of_date: str) -> dict:
    """Get the company's cash balance as of a date (wraps get_cash_balance). Internal only:
    never share this figure with customers.

    Args:
        as_of_date: Date in YYYY-MM-DD format.
    """
    as_of_date = _to_iso_date(as_of_date)
    return {"as_of_date": as_of_date, "cash_balance": round(get_cash_balance(as_of_date), 2)}


@tool
def restock_item(item_name: str, order_quantity: int, request_date: str, deadline_date: str) -> dict:
    """Check whether a customer order for one item can be served and reorder stock from the
    supplier when needed. Call this once per item of the customer order.

    The decision is deterministic:
    - enough stock and staying at/above the minimum stock level -> no purchase, available now;
    - otherwise it buys enough to cover the order AND restore the minimum stock level, as long as
      the company can afford it and (if the order depends on the delivery) the supplier delivers
      by the customer's deadline; if that larger order is too slow or too expensive it retries
      with just the shortfall;
    - if neither works the item is reported as unavailable with the reason.
    Purchases are recorded as 'stock_orders' transactions on the request date at the supplier's
    wholesale cost (70% of the catalog list price).

    Args:
        item_name: Exact catalog item name.
        order_quantity: Units the customer wants.
        request_date: Customer request date, YYYY-MM-DD.
        deadline_date: Date the customer needs delivery by, YYYY-MM-DD.
    """
    if item_name not in CATALOG:
        return _unknown_item_error(item_name)
    order_quantity = int(order_quantity)
    if order_quantity <= 0:
        return {"error": "order_quantity must be a positive integer."}
    request_date, deadline_date = _to_iso_date(request_date), _to_iso_date(deadline_date)

    stock = _stock_on(item_name, request_date)
    min_level = _min_stock_levels().get(item_name, 0)
    shortfall = max(0, order_quantity - stock)
    top_up = max(0, order_quantity + min_level - stock)  # restores min_level after the sale

    if top_up == 0:
        _log(f"restock_item({item_name}, {order_quantity}) -> in stock ({stock}), no reorder")
        return {"item_name": item_name, "status": "available", "restocked": False,
                "available_to_customer_on": request_date}

    unit_cost = CATALOG[item_name]["unit_price"] * SUPPLIER_COST_RATE
    cash = get_cash_balance(request_date)
    attempts = [top_up] + ([shortfall] if 0 < shortfall < top_up else [])
    rejection = ""
    for reorder_qty in attempts:
        supplier_date = get_supplier_delivery_date(request_date, reorder_qty)
        cost = round(reorder_qty * unit_cost, 2)
        if shortfall > 0 and supplier_date > deadline_date:
            rejection = (f"supplier cannot deliver {reorder_qty} units before {deadline_date} "
                         f"(earliest {supplier_date})")
            continue
        if cost > cash:
            rejection = "restocking cost exceeds available cash"
            continue
        create_transaction(item_name, "stock_orders", reorder_qty, cost, request_date)
        available_on = supplier_date if shortfall > 0 else request_date
        if shortfall > 0:
            key = (item_name, request_date)
            CUSTOMER_AVAILABILITY_DATES[key] = max(available_on, CUSTOMER_AVAILABILITY_DATES.get(key, ""))
        _log(f"restock_item({item_name}, {order_quantity}) -> bought {reorder_qty} for ${cost:.2f}, "
             f"supplier delivers {supplier_date}")
        return {"item_name": item_name, "status": "available", "restocked": True,
                "reorder_quantity": reorder_qty, "supplier_delivery_date": supplier_date,
                "available_to_customer_on": available_on}

    if shortfall == 0:
        # The order itself is covered by stock; only the top-up to min_level could not be placed.
        _log(f"restock_item({item_name}, {order_quantity}) -> in stock, top-up skipped: {rejection}")
        return {"item_name": item_name, "status": "available", "restocked": False,
                "available_to_customer_on": request_date, "note": f"replenishment skipped: {rejection}"}
    _log(f"restock_item({item_name}, {order_quantity}) -> UNAVAILABLE: {rejection}")
    return {"item_name": item_name, "status": "unavailable", "restocked": False, "reason": rejection}


# ---------------------------------------------------------------------------
# Tools for the quoting agent
# ---------------------------------------------------------------------------

@tool
def search_quote_history_tool(search_terms: list[str], limit: int = 5) -> list[dict]:
    """Find similar historical quotes (wraps search_quote_history). Each term is searched on its
    own and the results merged, because the underlying search requires ALL terms to match.

    Args:
        search_terms: Short keywords, e.g. ["cardstock", "ceremony"]. One or two words each.
        limit: Maximum number of quotes to return.
    """
    merged, seen = [], set()
    for term in search_terms:
        for quote in search_quote_history([term], limit=limit):
            key = (quote["total_amount"], quote["quote_explanation"][:60])
            if key not in seen:
                seen.add(key)
                merged.append({
                    "total_amount": quote["total_amount"],
                    "order_size": quote["order_size"],
                    "event_type": quote["event_type"],
                    "job_type": quote["job_type"],
                    "quote_explanation": quote["quote_explanation"][:300],
                })
    _log(f"search_quote_history_tool({search_terms}) -> {len(merged[:limit])} quotes")
    return merged[:limit]


@tool
def calculate_quote(items: list[dict], request_date: str, deadline_date: str) -> dict:
    """Price a set of items with catalog unit prices and the bulk-discount tier, and register
    the quote. Returns a quote_id that the sales agent needs to finalise the order.

    Bulk discount by total units: 500+ units 5%, 2,000+ units 10%, 10,000+ units 15%.
    Totals are rounded to whole dollars (friendly pricing, as in past quotes).

    Args:
        items: List of {"item_name": exact catalog name, "quantity": units} for the items to quote.
        request_date: Customer request date, YYYY-MM-DD.
        deadline_date: Date the customer needs delivery by, YYYY-MM-DD.
    """
    request_date, deadline_date = _to_iso_date(request_date), _to_iso_date(deadline_date)
    lines, errors = [], []
    for entry in items:
        name, quantity = entry.get("item_name"), int(entry.get("quantity", 0))
        if name not in CATALOG:
            errors.append(_unknown_item_error(str(name)))
        elif quantity <= 0:
            errors.append({"error": f"quantity for '{name}' must be positive"})
        else:
            unit_price = CATALOG[name]["unit_price"]
            lines.append({"item_name": name, "quantity": quantity, "unit_price": unit_price,
                          "list_price": round(quantity * unit_price, 2)})
    if not lines:
        return {"error": "no valid items to quote", "details": errors}

    total_units = sum(line["quantity"] for line in lines)
    discount_rate = next(rate for min_units, rate in BULK_DISCOUNT_TIERS if total_units >= min_units)
    list_total = sum(line["list_price"] for line in lines)
    discounted = list_total * (1 - discount_rate)
    total = float(round(discounted)) if discounted >= 1 else round(discounted, 2)

    # Spread the discount and rounding over the lines so booked sales add up to the quoted total
    factor = total / list_total
    for line in lines:
        line["line_total"] = round(line["list_price"] * factor, 2)
    lines[-1]["line_total"] = round(total - sum(line["line_total"] for line in lines[:-1]), 2)

    quote_id = f"Q-{request_date.replace('-', '')}-{len(QUOTES) + 1:03d}"
    QUOTES[quote_id] = {"quote_id": quote_id, "request_date": request_date, "deadline_date": deadline_date,
                        "lines": lines, "discount_rate": discount_rate, "list_total": round(list_total, 2),
                        "total": total, "status": "open"}
    _log(f"calculate_quote -> {quote_id}: {total_units} units, list ${list_total:.2f}, "
         f"{discount_rate:.0%} off, total ${total:.2f}")
    return {"quote_id": quote_id, "lines": lines, "total_units": total_units,
            "discount_rate": discount_rate, "list_total": round(list_total, 2), "total": total,
            "invalid_items": errors}


# ---------------------------------------------------------------------------
# Tools for the sales agent (also uses get_stock_level_tool and get_supplier_delivery_date_tool)
# ---------------------------------------------------------------------------

@tool
def generate_financial_report_tool(as_of_date: str) -> dict:
    """Company financial health check (wraps generate_financial_report): cash, inventory value,
    total assets, top sellers and items below minimum stock. Internal only: never share with
    customers. Use it before finalising large orders.

    Args:
        as_of_date: Date in YYYY-MM-DD format.
    """
    as_of_date = _to_iso_date(as_of_date)
    report = generate_financial_report(as_of_date)
    min_levels = _min_stock_levels()
    low_stock = [row["item_name"] for row in report["inventory_summary"]
                 if row["stock"] < min_levels.get(row["item_name"], 0)]
    _log(f"generate_financial_report_tool({as_of_date}) -> cash ${report['cash_balance']:.2f}")
    return {
        "as_of_date": as_of_date,
        "cash_balance": round(float(report["cash_balance"]), 2),
        "inventory_value": round(float(report["inventory_value"]), 2),
        "total_assets": round(float(report["total_assets"]), 2),
        # the $50k opening balance is seeded as a 'sale' without item name; not a real product
        "top_selling_products": [p for p in report["top_selling_products"] if p["item_name"]],
        "items_below_min_stock": low_stock,
    }


@tool
def fulfill_order(quote_id: str) -> dict:
    """Finalise an order from a quote: re-check stock and the delivery deadline for every quoted
    line and record each deliverable line as a 'sales' transaction at the quoted price.
    Calling it again for the same quote returns the original result (no double booking).

    Args:
        quote_id: The quote_id returned by calculate_quote, e.g. "Q-20250401-001".
    """
    quote = QUOTES.get(quote_id)
    if quote is None:
        return {"error": f"unknown quote_id '{quote_id}'"}
    if quote["status"] == "closed":
        return quote["fulfillment"]

    request_date, deadline_date = quote["request_date"], quote["deadline_date"]
    booked, rejected = [], []
    for line in quote["lines"]:
        name, quantity = line["item_name"], line["quantity"]
        available_on = CUSTOMER_AVAILABILITY_DATES.get((name, request_date), request_date)
        if available_on > deadline_date:
            rejected.append({"item_name": name, "reason": f"cannot be delivered by {deadline_date}"})
            continue
        if _stock_on(name, request_date) < quantity:
            rejected.append({"item_name": name, "reason": "insufficient stock"})
            continue
        transaction_id = create_transaction(name, "sales", quantity, line["line_total"], request_date)
        booked.append({"item_name": name, "quantity": quantity, "amount": line["line_total"],
                       "delivery_date": available_on, "transaction_id": transaction_id})

    status = "fulfilled" if not rejected else ("partially_fulfilled" if booked else "not_fulfilled")
    result = {
        "quote_id": quote_id,
        "status": status,
        "booked_lines": booked,
        "rejected_lines": rejected,
        "total_charged": round(sum(line["amount"] for line in booked), 2),
        "delivery_date": max((line["delivery_date"] for line in booked), default=None),
    }
    quote["status"], quote["fulfillment"] = "closed", result
    _log(f"fulfill_order({quote_id}) -> {status}, charged ${result['total_charged']:.2f}")
    return result


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------

INVENTORY_INSTRUCTIONS = """You are the Inventory Agent of the Beaver's Choice Paper Company.
You receive a request date, the customer's delivery deadline and a list of exact catalog item
names with quantities.
For EACH item call restock_item(item_name, order_quantity, request_date, deadline_date) exactly once.
It checks current stock, decides whether to reorder from the supplier (shortfall or dropping
below the minimum stock level), checks cash and supplier lead time against the deadline and
records any purchase. Never do these calculations yourself and never call it twice for an item.
Use get_stock_level_tool, get_all_inventory_tool, get_supplier_delivery_date_tool and
get_cash_balance_tool only for questions about stock, lead times or cash.
Your final answer must list one line per item, using only facts returned by the tools:
  <item_name> | <quantity> | AVAILABLE on <YYYY-MM-DD>
  <item_name> | <quantity> | UNAVAILABLE: <reason>"""

QUOTING_INSTRUCTIONS = """You are the Quoting Agent of the Beaver's Choice Paper Company.
You receive a request date, a delivery deadline, customer context (job, event, order size) and
the items to quote with exact catalog names and quantities.
1. Call search_quote_history_tool once with 1-3 short keywords (e.g. the event type and the main
   product) to see how similar past orders were priced and explained.
2. Call calculate_quote exactly once with all items. It applies catalog prices and the bulk
   discount deterministically. Never change, recompute or round its numbers.
Your final answer must contain: the quote_id, each line (item, quantity, unit price, line total),
the discount rate, the total, and one or two customer-friendly sentences explaining the bulk
discount (you may mention that it is in line with similar past orders)."""

SALES_INSTRUCTIONS = """You are the Sales Agent of the Beaver's Choice Paper Company.
You receive a quote_id, the quote total and the request date.
1. If the quote total is $1,000 or more, first call generate_financial_report_tool(request_date)
   as an internal health check. Its figures are confidential.
2. Call fulfill_order(quote_id) exactly once. It re-checks stock and deadlines and records the sale.
Your final answer must contain the order status, each booked line (item, quantity, amount,
delivery date), each rejected line with its reason, the total charged and the delivery date."""

ORCHESTRATOR_INSTRUCTIONS = f"""You are the customer-facing Orchestrator of the Beaver's Choice Paper Company.
You coordinate three specialist agents: inventory_agent, quoting_agent and sales_agent.
For every customer request follow these steps in order:
1. Read the request and determine:
   - request_date: the 'Date of request' given at the end (YYYY-MM-DD);
   - deadline_date: the date the customer needs delivery by, as YYYY-MM-DD (if none is given,
     use request_date + {DEFAULT_DELIVERY_WINDOW_DAYS} days);
   - every requested item with its quantity in single units. 1 ream = 500 sheets, so multiply
     reams by 500. Packs, boxes, rolls and similar count as the number stated.
2. Call match_catalog_items with the item descriptions exactly as the customer wrote them,
   without quantities. Items whose match is null are products we do not sell.
3. Call inventory_agent. In the task, give request_date, deadline_date and each matched item as
   '<exact catalog name>: <quantity>'.
4. Call quoting_agent with request_date, deadline_date, the customer context and ONLY the items
   inventory_agent reported as AVAILABLE, with their quantities.
5. Call sales_agent with the quote_id, the quote total and request_date to finalise the order.
   Skip steps 4 and 5 if no item is available.
6. Give your final answer: a friendly, concise reply to the customer that states, for every
   fulfilled item, the quantity and amount, the bulk discount applied, the total charged, the
   expected delivery date and the order reference (quote_id). For every requested item that was
   not fulfilled, say so and give a short reason (not part of our catalog / cannot be delivered
   by the requested date / insufficient stock).
Never reveal internal information: cash balance, stock levels, supplier details, costs,
margins or the names of internal agents and tools."""


class InventoryAgent(ToolCallingAgent):
    """Checks stock as of the request date and decides on reorders."""

    def __init__(self, model: OpenAIServerModel):
        super().__init__(
            tools=[get_stock_level_tool, get_all_inventory_tool, get_supplier_delivery_date_tool,
                   get_cash_balance_tool, restock_item],
            model=model,
            name="inventory_agent",
            description=("Checks availability of catalog items for a customer order and reorders "
                         "stock from the supplier when needed. Give it the request date, the "
                         "delivery deadline and '<exact catalog name>: <quantity>' for each item."),
            instructions=INVENTORY_INSTRUCTIONS,
            max_steps=12,
            verbosity_level=AGENT_VERBOSITY,
        )


class QuotingAgent(ToolCallingAgent):
    """Prices available items with bulk discounts, informed by historical quotes."""

    def __init__(self, model: OpenAIServerModel):
        super().__init__(
            tools=[search_quote_history_tool, calculate_quote],
            model=model,
            name="quoting_agent",
            description=("Produces a priced quote with bulk discounts and returns a quote_id. Give "
                         "it the request date, the delivery deadline, the customer context and "
                         "the available items as '<exact catalog name>: <quantity>'."),
            instructions=QUOTING_INSTRUCTIONS,
            max_steps=6,
            verbosity_level=AGENT_VERBOSITY,
        )


class SalesAgent(ToolCallingAgent):
    """Finalises orders from quotes and records the sales transactions."""

    def __init__(self, model: OpenAIServerModel):
        super().__init__(
            tools=[get_stock_level_tool, get_supplier_delivery_date_tool,
                   generate_financial_report_tool, fulfill_order],
            model=model,
            name="sales_agent",
            description=("Finalises a customer order from a quote and records the sale. Give it the "
                         "quote_id, the quote total and the request date."),
            instructions=SALES_INSTRUCTIONS,
            max_steps=6,
            verbosity_level=AGENT_VERBOSITY,
        )


class OrchestratorAgent(ToolCallingAgent):
    """Customer-facing coordinator that delegates to the three worker agents."""

    def __init__(self, model: OpenAIServerModel):
        super().__init__(
            tools=[match_catalog_items],
            model=model,
            managed_agents=[InventoryAgent(model), QuotingAgent(model), SalesAgent(model)],
            name="orchestrator",
            description="Handles customer inquiries for the Beaver's Choice Paper Company.",
            instructions=ORCHESTRATOR_INSTRUCTIONS,
            max_steps=12,
            verbosity_level=AGENT_VERBOSITY,
        )


def handle_customer_request(orchestrator: OrchestratorAgent, request_text: str) -> str:
    """Run one customer request through the multi-agent system and return the customer reply."""
    try:
        return str(orchestrator.run(request_text))
    except Exception as exc:  # keep the test run going; the failure is logged, not shown to the customer
        print(f"ERROR while handling request: {exc}")
        return ("We're sorry, we could not process your request right now. "
                "A member of our team will follow up with you shortly.")


# Run your test scenarios by writing them here. Make sure to keep track of them.

def run_test_scenarios():

    print("Initializing Database...")
    init_database(db_engine)
    reset_session_state()
    try:
        quote_requests_sample = pd.read_csv("quote_requests_sample.csv")
        quote_requests_sample["request_date"] = pd.to_datetime(
            quote_requests_sample["request_date"], format="%m/%d/%y", errors="coerce"
        )
        quote_requests_sample.dropna(subset=["request_date"], inplace=True)
        quote_requests_sample = quote_requests_sample.sort_values("request_date")
    except Exception as e:
        print(f"FATAL: Error loading test data: {e}")
        return

    # Get initial state
    initial_date = quote_requests_sample["request_date"].min().strftime("%Y-%m-%d")
    report = generate_financial_report(initial_date)
    current_cash = report["cash_balance"]
    current_inventory = report["inventory_value"]

    ############
    ############
    ############
    # INITIALIZE YOUR MULTI AGENT SYSTEM HERE
    ############
    ############
    ############

    orchestrator = OrchestratorAgent(build_model())

    results = []
    for idx, row in quote_requests_sample.iterrows():
        request_date = row["request_date"].strftime("%Y-%m-%d")

        print(f"\n=== Request {idx+1} ===")
        print(f"Context: {row['job']} organizing {row['event']}")
        print(f"Request Date: {request_date}")
        print(f"Cash Balance: ${current_cash:.2f}")
        print(f"Inventory Value: ${current_inventory:.2f}")

        # Process request
        request_with_date = f"{row['request']} (Date of request: {request_date})"

        ############
        ############
        ############
        # USE YOUR MULTI AGENT SYSTEM TO HANDLE THE REQUEST
        ############
        ############
        ############

        customer_context = f"Customer context: {row['job']} organizing a {row['event']} ({row['need_size']} order).\n"
        response = handle_customer_request(orchestrator, customer_context + request_with_date)

        # Update state
        report = generate_financial_report(request_date)
        current_cash = report["cash_balance"]
        current_inventory = report["inventory_value"]

        print(f"Response: {response}")
        print(f"Updated Cash: ${current_cash:.2f}")
        print(f"Updated Inventory: ${current_inventory:.2f}")

        results.append(
            {
                "request_id": idx + 1,
                "request_date": request_date,
                "cash_balance": current_cash,
                "inventory_value": current_inventory,
                "response": response,
            }
        )

        time.sleep(1)

    # Final report
    final_date = quote_requests_sample["request_date"].max().strftime("%Y-%m-%d")
    final_report = generate_financial_report(final_date)
    print("\n===== FINAL FINANCIAL REPORT =====")
    print(f"Final Cash: ${final_report['cash_balance']:.2f}")
    print(f"Final Inventory: ${final_report['inventory_value']:.2f}")

    # Save results
    pd.DataFrame(results).to_csv("test_results.csv", index=False)
    return results


if __name__ == "__main__":
    results = run_test_scenarios()
