import streamlit as st
import sqlite3
import pandas as pd
import qrcode
import barcode
from barcode.writer import ImageWriter
import cv2
from pyzbar.pyzbar import decode
from datetime import datetime
from reportlab.platypus import (
    SimpleDocTemplate,
    Image as RLImage,
    Spacer
)
import bcrypt
import os

# ============================================================
# CREATE FOLDERS
# ============================================================

os.makedirs("qr_codes", exist_ok=True)
os.makedirs("barcodes", exist_ok=True)
os.makedirs("labels", exist_ok=True)

# ============================================================
# DATABASE
# ============================================================

conn = sqlite3.connect(
    "inventory.db",
    check_same_thread=False
)

cursor = conn.cursor()

# ============================================================
# TABLES
# ============================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS master_products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT UNIQUE
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS stores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    store_name TEXT UNIQUE
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password BLOB,
    role TEXT,
    store_id INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_code TEXT UNIQUE,
    product_name TEXT,
    quantity_per_pack INTEGER,
    pack_price REAL,
    single_price REAL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS product_packs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pack_code TEXT UNIQUE,
    product_code TEXT,
    product_name TEXT,
    total_units INTEGER,
    remaining_units INTEGER,
    store_id INTEGER,
    status TEXT,
    created_by TEXT,
    created_at TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS scan_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    store_id INTEGER,
    pack_code TEXT,
    product_name TEXT,
    quantity_sold INTEGER,
    total_amount REAL,
    scan_time TEXT
)
""")

conn.commit()

# ============================================================
# PASSWORD FUNCTIONS
# ============================================================

def hash_password(password):
    return bcrypt.hashpw(
        password.encode(),
        bcrypt.gensalt()
    )

def verify_password(password, hashed):
    return bcrypt.checkpw(
        password.encode(),
        hashed
    )

# ============================================================
# LOGIN
# ============================================================

def login_user(username, password):

    cursor.execute(
        """
        SELECT * FROM users
        WHERE username = ?
        """,
        (username,)
    )

    user = cursor.fetchone()

    if user:

        if verify_password(
            password,
            user[2]
        ):
            return user

    return None

# ============================================================
# CREATE DEFAULT ADMIN
# ============================================================

cursor.execute("""
SELECT * FROM users
WHERE username='admin'
""")

admin_check = cursor.fetchone()

if not admin_check:

    admin_password = hash_password(
        "admin123"
    )

    cursor.execute("""
    INSERT INTO users (
        username,
        password,
        role,
        store_id
    )
    VALUES (?, ?, ?, ?)
    """, (
        "admin",
        admin_password,
        "ADMIN",
        0
    ))

    conn.commit()

# ============================================================
# QR GENERATOR
# ============================================================

def generate_qr(pack_code):

    qr = qrcode.make(pack_code)

    path = f"qr_codes/{pack_code}.png"

    qr.save(path)

# ============================================================
# BARCODE GENERATOR
# ============================================================

def generate_barcode(pack_code):

    code128 = barcode.get(
        "code128",
        pack_code,
        writer=ImageWriter()
    )

    code128.save(
        f"barcodes/{pack_code}"
    )

# ============================================================
# PDF LABEL GENERATOR
# ============================================================

def generate_combined_pdf(
    product_code,
    number_of_packs
):

    pdf_path = (
        f"labels/{product_code}_labels.pdf"
    )

    doc = SimpleDocTemplate(pdf_path)

    elements = []

    for i in range(
        1,
        number_of_packs + 1
    ):

        pack_code = (
            f"{product_code}-PACK-{i:05d}"
        )

        qr_path = (
            f"qr_codes/{pack_code}.png"
        )

        barcode_path = (
            f"barcodes/{pack_code}.png"
        )

        qr_img = RLImage(
            qr_path,
            width=60,
            height=60
        )

        elements.append(qr_img)
        elements.append(Spacer(1, 10))

    doc.build(elements)

    return pdf_path

# ============================================================
# SCANNER
# ============================================================

uploaded_file = st.camera_input(
    "Scan QR / Barcode"
)

if uploaded_file is not None:

    image_bytes = uploaded_file.getvalue()

    with open(
        "temp_scan.png",
        "wb"
    ) as f:
        f.write(image_bytes)

    image = cv2.imread(
        "temp_scan.png"
    )

    detected = decode(image)

    for code in detected:

        scanned_code = (
            code.data.decode('utf-8')
        )

        st.session_state.scanned_code = (
            scanned_code
        )
        
# ============================================================
# STREAMLIT CONFIG
# ============================================================

st.set_page_config(
    page_title="Inventory ERP",
    layout="wide"
)

st.title("Inventory ERP System")

# ============================================================
# SESSION STATE
# ============================================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "scanned_code" not in st.session_state:
    st.session_state.scanned_code = None

# ============================================================
# LOGIN PAGE
# ============================================================

if not st.session_state.logged_in:

    st.header("Login")

    username = st.text_input(
        "Username"
    )

    password = st.text_input(
        "Password",
        type="password"
    )

    if st.button("Login"):

        user = login_user(
            username,
            password
        )

        if user:

            st.session_state.logged_in = True
            st.session_state.username = user[1]
            st.session_state.role = user[3]
            st.session_state.store_id = user[4]

            st.success(
                "Login Successful"
            )

            st.rerun()

        else:
            st.error(
                "Invalid Credentials"
            )

    st.stop()

# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.success(
    f"Logged in as {st.session_state.username}"
)

menu = st.sidebar.selectbox(
    "Menu",
    [
        "Dashboard",
        "Create Store",
        "Create User",
        "Master Products",
        "Add Product",
        "Scan Product",
        "Inventory",
        "Scan History"
    ]
)

# ============================================================
# DASHBOARD
# ============================================================

if menu == "Dashboard":

    st.header("Dashboard")

    if st.session_state.role == "ADMIN":

        products = pd.read_sql_query(
            """
            SELECT COUNT(*) as total
            FROM products
            """,
            conn
        )

        stores = pd.read_sql_query(
            """
            SELECT COUNT(*) as total
            FROM stores
            """,
            conn
        )

        users = pd.read_sql_query(
            """
            SELECT COUNT(*) as total
            FROM users
            """,
            conn
        )

        inventory = pd.read_sql_query(
            """
            SELECT SUM(remaining_units)
            as total
            FROM product_packs
            """,
            conn
        )

        sales = pd.read_sql_query(
            """
            SELECT SUM(total_amount)
            as total
            FROM scan_history
            """,
            conn
        )

        col1, col2, col3, col4, col5 = (
            st.columns(5)
        )

        col1.metric(
            "Products",
            products["total"][0]
        )

        col2.metric(
            "Stores",
            stores["total"][0]
        )

        col3.metric(
            "Users",
            users["total"][0]
        )

        col4.metric(
            "Remaining Units",
            inventory["total"][0]
        )

        col5.metric(
            "Sales ₹",
            round(
                sales["total"][0]
                if sales["total"][0]
                else 0,
                2
            )
        )

        st.divider()

        st.subheader(
            "Store Wise Inventory"
        )

        store_query = """

        SELECT

            s.store_name,

            COUNT(pp.id)
            as total_packs,

            SUM(pp.remaining_units)
            as remaining_units,

            ROUND(
                SUM(
                    pp.remaining_units
                    * p.single_price
                ),
                2
            ) as stock_value,

            ROUND(
                IFNULL(
                    (
                        SELECT SUM(
                            sh.total_amount
                        )
                        FROM scan_history sh
                        WHERE sh.store_id = s.id
                    ),
                    0
                ),
                2
            ) as sold_value

        FROM stores s

        LEFT JOIN product_packs pp
            ON s.id = pp.store_id

        LEFT JOIN products p
            ON pp.product_code
            = p.product_code

        GROUP BY s.store_name

        """

        store_df = pd.read_sql_query(
            store_query,
            conn
        )

        st.dataframe(
            store_df,
            use_container_width=True
        )

    else:

        inventory = pd.read_sql_query(f"""
        SELECT SUM(remaining_units)
        as total
        FROM product_packs
        WHERE store_id =
        {st.session_state.store_id}
        """, conn)

        history = pd.read_sql_query(f"""
        SELECT COUNT(*) as total
        FROM scan_history
        WHERE username =
        '{st.session_state.username}'
        """, conn)

        sales = pd.read_sql_query(f"""
        SELECT SUM(total_amount)
        as total
        FROM scan_history
        WHERE username =
        '{st.session_state.username}'
        """, conn)

        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Store Inventory",
            inventory["total"][0]
        )

        col2.metric(
            "My Scans",
            history["total"][0]
        )

        col3.metric(
            "My Sales ₹",
            round(
                sales["total"][0]
                if sales["total"][0]
                else 0,
                2
            )
        )

# ============================================================
# CREATE STORE
# ============================================================

elif menu == "Create Store":

    if st.session_state.role != "ADMIN":
        st.stop()

    st.header("Create Store")

    store_name = st.text_input(
        "Store Name"
    )

    if st.button("Create Store"):

        cursor.execute("""
        INSERT INTO stores (
            store_name
        )
        VALUES (?)
        """, (store_name,))

        conn.commit()

        st.success("Store Created")

# ============================================================
# CREATE USER
# ============================================================

elif menu == "Create User":

    if st.session_state.role != "ADMIN":
        st.stop()

    st.header("Create User")

    cursor.execute(
        "SELECT * FROM stores"
    )

    stores = cursor.fetchall()

    store_map = {
        store[1]: store[0]
        for store in stores
    }

    username = st.text_input(
        "Username"
    )

    password = st.text_input(
        "Password",
        type="password"
    )

    role = st.selectbox(
        "Role",
        ["ADMIN", "USER"]
    )

    store_name = st.selectbox(
        "Store",
        list(store_map.keys())
    )

    if st.button("Create User"):

        hashed = hash_password(password)

        cursor.execute("""
        INSERT INTO users (
            username,
            password,
            role,
            store_id
        )
        VALUES (?, ?, ?, ?)
        """, (
            username,
            hashed,
            role,
            store_map[store_name]
        ))

        conn.commit()

        st.success("User Created")

# ============================================================
# MASTER PRODUCTS
# ============================================================

elif menu == "Master Products":

    if st.session_state.role != "ADMIN":
        st.stop()

    st.header("Master Products")

    product_name = st.text_input(
        "Product Name"
    )

    if st.button(
        "Add Master Product"
    ):

        cursor.execute("""
        INSERT INTO master_products (
            product_name
        )
        VALUES (?)
        """, (product_name,))

        conn.commit()

        st.success(
            "Master Product Added"
        )

    master_df = pd.read_sql_query(
        """
        SELECT *
        FROM master_products
        """,
        conn
    )

    st.dataframe(master_df)

# ============================================================
# ADD PRODUCT
# ============================================================

elif menu == "Add Product":

    if st.session_state.role != "ADMIN":
        st.stop()

    st.header("Add Product")

    cursor.execute("""
    SELECT product_name
    FROM master_products
    """)

    master_products = cursor.fetchall()

    product_options = [
        product[0]
        for product in master_products
    ]

    cursor.execute(
        "SELECT * FROM stores"
    )

    stores = cursor.fetchall()

    store_map = {
        store[1]: store[0]
        for store in stores
    }

    product_code = st.text_input(
        "Product Code"
    )

    product_name = st.selectbox(
        "Select Product",
        product_options
    )

    quantity_per_pack = st.number_input(
        "Quantity Per Pack",
        min_value=1
    )

    pack_price = st.number_input(
        "Pack Price",
        min_value=1.0
    )

    number_of_packs = st.number_input(
        "Number Of Packs",
        min_value=1
    )

    store_name = st.selectbox(
        "Store",
        list(store_map.keys())
    )

    if st.button("Add Product"):

        single_price = (
            pack_price /
            quantity_per_pack
        )

        cursor.execute("""
        INSERT INTO products (
            product_code,
            product_name,
            quantity_per_pack,
            pack_price,
            single_price
        )
        VALUES (?, ?, ?, ?, ?)
        """, (
            product_code,
            product_name,
            quantity_per_pack,
            pack_price,
            single_price
        ))

        for i in range(
            1,
            number_of_packs + 1
        ):

            pack_code = (
                f"{product_code}-PACK-{i:05d}"
            )

            cursor.execute("""
            INSERT INTO product_packs (
                pack_code,
                product_code,
                product_name,
                total_units,
                remaining_units,
                store_id,
                status,
                created_by,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pack_code,
                product_code,
                product_name,
                quantity_per_pack,
                quantity_per_pack,
                store_map[store_name],
                "ACTIVE",
                st.session_state.username,
                datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            ))

            generate_qr(pack_code)
            generate_barcode(pack_code)

        conn.commit()

        pdf_path = generate_combined_pdf(
            product_code,
            number_of_packs
        )

        st.success(
            "Product Added Successfully"
        )

        with open(
            pdf_path,
            "rb"
        ) as file:

            st.download_button(
                label="Download Labels",
                data=file,
                file_name=
                f"{product_code}_labels.pdf",
                mime="application/pdf"
            )

# ============================================================
# SCAN PRODUCT
# ============================================================

elif menu == "Scan Product":

    st.header("Scan Product")

    if st.button("Open Scanner"):

        scanned = scan_code()

        if scanned:
            st.session_state.scanned_code = (
                scanned
            )

    if st.session_state.scanned_code:

        code = (
            st.session_state.scanned_code
        )

        st.success(
            f"Scanned: {code}"
        )

        cursor.execute("""
        SELECT * FROM product_packs
        WHERE pack_code = ?
        """, (code,))

        pack = cursor.fetchone()

        if pack:

            remaining_units = pack[5]

            st.write(
                f"Product: {pack[3]}"
            )

            st.write(
                f"Remaining Units: "
                f"{remaining_units}"
            )

            quantity = st.number_input(
                "Quantity Sold",
                min_value=1,
                value=1
            )

            if st.button("Sell Product"):

                if quantity > remaining_units:

                    st.error(
                        f"Only "
                        f"{remaining_units} "
                        f"remaining in this pack"
                    )

                else:

                    new_quantity = (
                        remaining_units
                        - quantity
                    )

                    status = "ACTIVE"

                    if new_quantity == 0:
                        status = "EMPTY"

                    cursor.execute("""
                    UPDATE product_packs
                    SET remaining_units = ?,
                        status = ?
                    WHERE pack_code = ?
                    """, (
                        new_quantity,
                        status,
                        code
                    ))

                    cursor.execute("""
                    SELECT single_price
                    FROM products
                    WHERE product_code = ?
                    """, (pack[2],))

                    price_data = (
                        cursor.fetchone()
                    )

                    single_price = (
                        price_data[0]
                    )

                    total_amount = (
                        quantity
                        * single_price
                    )

                    cursor.execute("""
                    INSERT INTO scan_history (
                        username,
                        store_id,
                        pack_code,
                        product_name,
                        quantity_sold,
                        total_amount,
                        scan_time
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        st.session_state.username,
                        st.session_state.store_id,
                        code,
                        pack[3],
                        quantity,
                        total_amount,
                        datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                    ))

                    conn.commit()

                    st.success(
                        "Sale Completed"
                    )

                    st.session_state.scanned_code = None

                    st.rerun()

# ============================================================
# INVENTORY
# ============================================================

elif menu == "Inventory":

    st.header("Inventory")

    if st.session_state.role == "ADMIN":

        query = """
        SELECT * FROM product_packs
        """

    else:

        query = f"""
        SELECT *
        FROM product_packs
        WHERE store_id =
        {st.session_state.store_id}
        """

    inventory_df = pd.read_sql_query(
        query,
        conn
    )

    st.dataframe(
        inventory_df,
        use_container_width=True
    )

    st.metric(
        "Total Remaining Units",
        inventory_df[
            "remaining_units"
        ].sum()
    )

# ============================================================
# SCAN HISTORY
# ============================================================

elif menu == "Scan History":

    st.header("Scan History")

    if st.session_state.role == "ADMIN":

        query = """
        SELECT *
        FROM scan_history
        """

    else:

        query = f"""
        SELECT *
        FROM scan_history
        WHERE username =
        '{st.session_state.username}'
        """

    history_df = pd.read_sql_query(
        query,
        conn
    )

    st.dataframe(
        history_df,
        use_container_width=True
    )