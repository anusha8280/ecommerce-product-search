import sys
import os
from datetime import datetime

# Add services/api to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "services", "api")))

from app.database import SessionLocal, init_db
from app.models.product import Category, Brand, Product, User, UserActivity
from app.schemas.product import ProductCreate, ProductUpdate
from app.services.product_service import product_service
from app.infrastructure import opensearch_client


def seed():
    print("Starting data seeding process...")
    init_db()
    db = SessionLocal()

    try:
        # Keep the seed additive: never delete existing catalog or user data.
        categories_data = [
            {"name": "Electronics", "description": "Consumer electronics and personal technology"},
            {"name": "Clothing", "description": "Everyday apparel and activewear"},
            {"name": "Shoes", "description": "Casual, running, and athletic footwear"},
            {"name": "Home", "description": "Practical appliances and home furnishings"},
            {"name": "Books", "description": "Popular fiction and personal development titles"},
            # Retain categories used by the original sample records.
            {"name": "Audio & Headphones", "description": "Headphones, earbuds, and speakers"},
            {"name": "Computers & Gaming", "description": "Laptops, gaming mice, and keyboards"},
            {"name": "Wearable Tech", "description": "Smartwatches and fitness trackers"},
            {"name": "Mobile Accessories", "description": "Chargers, cables, and cases"}
        ]
        categories = {}
        for c in categories_data:
            cat = db.query(Category).filter(Category.name == c["name"]).first()
            if cat is None:
                cat = Category(name=c["name"], description=c["description"])
                db.add(cat)
                db.flush()
            elif cat.description != c["description"]:
                cat.description = c["description"]
            categories[c["name"]] = cat.id
        db.commit()

        print(f"Ensured {len(categories)} seed categories.")

        # 3. Seed Brands
        brands_data = [
            {"name": "Sony", "description": "Consumer electronics manufacturer"},
            {"name": "Apple", "description": "Premium tech products"},
            {"name": "Logitech", "description": "Computer peripherals"},
            {"name": "Samsung", "description": "Smartphones and displays"},
            {"name": "Bose", "description": "Premium audio equipment"},
            {"name": "Anker", "description": "Charging and mobile accessories"},
            {"name": "Dell", "description": "Computers and business technology"},
            {"name": "Nike", "description": "Athletic apparel and footwear"},
            {"name": "Levi's", "description": "Denim apparel"},
            {"name": "Adidas", "description": "Sportswear and athletic footwear"},
            {"name": "Converse", "description": "Casual canvas footwear"},
            {"name": "Dyson", "description": "Home cleaning appliances"},
            {"name": "Instant Pot", "description": "Kitchen appliances"},
            {"name": "IKEA", "description": "Home furnishings and accessories"},
            {"name": "Penguin Random House", "description": "Trade book publisher"}
        ]
        brands = {}
        for b in brands_data:
            brand = db.query(Brand).filter(Brand.name == b["name"]).first()
            if brand is None:
                brand = Brand(name=b["name"], description=b["description"])
                db.add(brand)
                db.flush()
            elif brand.description != b["description"]:
                brand.description = b["description"]
            brands[b["name"]] = brand.id
        db.commit()

        print(f"Ensured {len(brands)} seed brands.")

        # 4. Seed Products
        products_data = [
            {
                "name": "Sony WH-1000XM5 Wireless Noise-Canceling Headphones",
                "description": "Industry-leading noise cancellation with two processors and eight microphones.",
                "price": 399.99,
                "category_id": categories["Audio & Headphones"],
                "brand_id": brands["Sony"],
                "rating": 4.8,
                "stock_quantity": 150,
                "is_available": True,
                "attributes": [
                    {"name": "Color", "value": "Black"},
                    {"name": "Battery Life", "value": "30 Hours"},
                    {"name": "Connectivity", "value": "Bluetooth 5.2"}
                ]
            },
            {
                "name": "Bose QuietComfort Ultra Earbuds",
                "description": "Breakthrough spatial audio and world-class noise cancellation.",
                "price": 299.00,
                "category_id": categories["Audio & Headphones"],
                "brand_id": brands["Bose"],
                "rating": 4.6,
                "stock_quantity": 80,
                "is_available": True,
                "attributes": [
                    {"name": "Color", "value": "White Smoke"},
                    {"name": "Water Resistance", "value": "IPX4"}
                ]
            },
            {
                "name": "Logitech MX Master 3S Wireless Mouse",
                "description": "Performance wireless mouse with 8K DPI tracking on glass and quiet clicks.",
                "price": 99.99,
                "category_id": categories["Computers & Gaming"],
                "brand_id": brands["Logitech"],
                "rating": 4.9,
                "stock_quantity": 200,
                "is_available": True,
                "attributes": [
                    {"name": "Color", "value": "Graphite"},
                    {"name": "DPI", "value": "8000"}
                ]
            },
            {
                "name": "Logitech G Pro X Superlight Gaming Mouse",
                "description": "Ultra-lightweight wireless gaming mouse engineered for esports athletes.",
                "price": 149.99,
                "category_id": categories["Computers & Gaming"],
                "brand_id": brands["Logitech"],
                "rating": 4.7,
                "stock_quantity": 120,
                "is_available": True,
                "attributes": [
                    {"name": "Weight", "value": "63g"},
                    {"name": "Sensor", "value": "HERO 25K"}
                ]
            },
            {
                "name": "Apple Watch Series 9 GPS 45mm",
                "description": "Smarter, brighter, and more powerful smartwatch with Double Tap gesture.",
                "price": 429.00,
                "category_id": categories["Wearable Tech"],
                "brand_id": brands["Apple"],
                "rating": 4.8,
                "stock_quantity": 90,
                "is_available": True,
                "attributes": [
                    {"name": "Case Size", "value": "45mm"},
                    {"name": "Band Color", "value": "Midnight"}
                ]
            },
            {
                "name": "Samsung Galaxy Watch6 Classic 47mm",
                "description": "Iconic rotating bezel smartwatch with comprehensive body composition analysis.",
                "price": 379.99,
                "category_id": categories["Wearable Tech"],
                "brand_id": brands["Samsung"],
                "rating": 4.5,
                "stock_quantity": 60,
                "is_available": True,
                "attributes": [
                    {"name": "Size", "value": "47mm"},
                    {"name": "Color", "value": "Silver"}
                ]
            },
            {
                "name": "Anker 65W Fast USB-C Charger",
                "description": "Compact high-speed wall charger powered by GaN II technology.",
                "price": 34.99,
                "category_id": categories["Mobile Accessories"],
                "brand_id": brands["Anker"],
                "rating": 4.7,
                "stock_quantity": 300,
                "is_available": True,
                "attributes": [
                    {"name": "Output Power", "value": "65W"},
                    {"name": "Ports", "value": "2 USB-C, 1 USB-A"}
                ]
            },
            {
                "name": "Apple MagSafe Battery Pack",
                "description": "Attaches seamlessly to iPhone for wireless magnetic charging on the go.",
                "price": 99.00,
                "category_id": categories["Mobile Accessories"],
                "brand_id": brands["Apple"],
                "rating": 4.3,
                "stock_quantity": 50,
                "is_available": True,
                "attributes": [
                    {"name": "Color", "value": "White"},
                    {"name": "Compatibility", "value": "iPhone 12 and newer"}
                ]
            },
            {
                "name": "Dell XPS 13 Plus Laptop",
                "description": "Compact premium laptop with a 13.4-inch display, Intel Core processor, and 16 GB memory.",
                "price": 1299.00,
                "category_id": categories["Electronics"],
                "brand_id": brands["Dell"],
                "rating": 4.6,
                "stock_quantity": 35,
                "is_available": True,
                "attributes": [
                    {"name": "Memory", "value": "16 GB"},
                    {"name": "Display", "value": "13.4-inch"}
                ]
            },
            {
                "name": "Apple iPhone 15 128GB",
                "description": "Unlocked smartphone with a 6.1-inch OLED display and dual-camera system.",
                "price": 699.00,
                "category_id": categories["Electronics"],
                "brand_id": brands["Apple"],
                "rating": 4.7,
                "stock_quantity": 42,
                "is_available": True,
                "attributes": [
                    {"name": "Storage", "value": "128 GB"},
                    {"name": "Color", "value": "Blue"}
                ]
            },
            {
                "name": "Anker 737 Power Bank 24000mAh",
                "description": "Portable USB-C power bank with 140W output for phones, tablets, and laptops.",
                "price": 109.99,
                "category_id": categories["Electronics"],
                "brand_id": brands["Anker"],
                "rating": 4.6,
                "stock_quantity": 75,
                "is_available": True,
                "attributes": [
                    {"name": "Capacity", "value": "24000 mAh"},
                    {"name": "Output", "value": "140W USB-C"}
                ]
            },
            {
                "name": "Nike Dri-FIT Training T-Shirt",
                "description": "Lightweight short-sleeve training shirt made with sweat-wicking fabric.",
                "price": 35.00,
                "category_id": categories["Clothing"],
                "brand_id": brands["Nike"],
                "rating": 4.5,
                "stock_quantity": 110,
                "is_available": True,
                "attributes": [
                    {"name": "Color", "value": "Black"},
                    {"name": "Material", "value": "Polyester"},
                    {"name": "Sizes", "value": "S-XXL"}
                ]
            },
            {
                "name": "Levi's 501 Original Fit Jeans",
                "description": "Classic straight-leg denim jeans with a button fly and five-pocket styling.",
                "price": 79.50,
                "category_id": categories["Clothing"],
                "brand_id": brands["Levi's"],
                "rating": 4.4,
                "stock_quantity": 64,
                "is_available": True,
                "attributes": [
                    {"name": "Fit", "value": "Straight"},
                    {"name": "Material", "value": "Cotton denim"}
                ]
            },
            {
                "name": "Adidas Ultraboost 22 Running Shoes",
                "description": "Responsive road-running shoes with a cushioned midsole and knit upper.",
                "price": 189.99,
                "category_id": categories["Shoes"],
                "brand_id": brands["Adidas"],
                "rating": 4.6,
                "stock_quantity": 48,
                "is_available": True,
                "attributes": [
                    {"name": "Color", "value": "Core Black"},
                    {"name": "Closure", "value": "Lace-up"}
                ]
            },
            {
                "name": "Converse Chuck 70 High Top Sneakers",
                "description": "Canvas high-top sneakers with a vintage-inspired silhouette and cushioned footbed.",
                "price": 90.00,
                "category_id": categories["Shoes"],
                "brand_id": brands["Converse"],
                "rating": 4.5,
                "stock_quantity": 57,
                "is_available": True,
                "attributes": [
                    {"name": "Color", "value": "Parchment"},
                    {"name": "Upper", "value": "Canvas"}
                ]
            },
            {
                "name": "Dyson V8 Cordless Vacuum Cleaner",
                "description": "Cordless stick vacuum with a motorized cleaner head and up to 40 minutes of runtime.",
                "price": 399.99,
                "category_id": categories["Home"],
                "brand_id": brands["Dyson"],
                "rating": 4.5,
                "stock_quantity": 22,
                "is_available": True,
                "attributes": [
                    {"name": "Runtime", "value": "Up to 40 minutes"},
                    {"name": "Type", "value": "Cordless stick vacuum"}
                ]
            },
            {
                "name": "Instant Pot Duo 7-in-1 Electric Pressure Cooker",
                "description": "Multi-use cooker for pressure cooking, slow cooking, steaming, and rice preparation.",
                "price": 99.95,
                "category_id": categories["Home"],
                "brand_id": brands["Instant Pot"],
                "rating": 4.7,
                "stock_quantity": 68,
                "is_available": True,
                "attributes": [
                    {"name": "Capacity", "value": "6 quart"},
                    {"name": "Functions", "value": "7-in-1"}
                ]
            },
            {
                "name": "Atomic Habits: An Easy & Proven Way to Build Good Habits",
                "description": "James Clear's practical guide to building better habits through small, consistent changes.",
                "price": 18.99,
                "category_id": categories["Books"],
                "brand_id": brands["Penguin Random House"],
                "rating": 4.8,
                "stock_quantity": 140,
                "is_available": True,
                "attributes": [
                    {"name": "Author", "value": "James Clear"},
                    {"name": "Format", "value": "Paperback"}
                ]
            }
        ]

        seeded_products = []
        for p in products_data:
            attribute_data = [
                {"attribute_name": item["name"], "attribute_value": item["value"]}
                for item in p["attributes"]
            ]
            product = db.query(Product).filter(Product.name == p["name"]).first()

            if product is None:
                # Use the existing product service so normal OpenSearch and Kafka
                # create-event behavior remains the single source of truth.
                product = product_service.create_product(
                    db,
                    ProductCreate(
                        name=p["name"],
                        description=p["description"],
                        price=p["price"],
                        category_id=p["category_id"],
                        brand_id=p["brand_id"],
                        stock_quantity=p["stock_quantity"],
                        is_available=p["is_available"],
                        attributes=attribute_data
                    )
                )

            # Align an existing seed product if its canonical seed data changed.
            updates = {}
            for field in (
                "description", "price", "category_id", "brand_id", "rating",
                "stock_quantity", "is_available"
            ):
                current_value = getattr(product, field)
                expected_value = p[field]
                if field in ("price", "rating"):
                    current_value = float(current_value or 0)
                    expected_value = float(expected_value)
                if current_value != expected_value:
                    updates[field] = expected_value

            existing_attributes = {
                (item.attribute_name, item.attribute_value)
                for item in product.attributes
            }
            expected_attributes = {
                (item["attribute_name"], item["attribute_value"])
                for item in attribute_data
            }
            if existing_attributes != expected_attributes:
                updates["attributes"] = attribute_data

            if updates:
                product = product_service.update_product(
                    db, product.id, ProductUpdate(**updates)
                )

            seeded_products.append(product)

            # Reindex existing and newly seeded products by stable product ID.
            # The shared OpenSearch client makes reruns overwrite, not duplicate,
            # the corresponding search document.
            index_document = product_service._product_to_dict(product)
            indexed = opensearch_client.index_product(index_document)
            if not indexed:
                print(f"[Warning] OpenSearch did not index product {product.id}.")

        print(f"Ensured {len(seeded_products)} products with attributes.")

        # 5. Ensure sample users and activities without duplicating existing rows.
        users_data = [
            {"name": "Alice Johnson", "email": "alice@example.com"},
            {"name": "Bob Smith", "email": "bob@example.com"}
        ]
        users = {}
        for data in users_data:
            user = db.query(User).filter(User.email == data["email"]).first()
            if user is None:
                user = User(**data)
                db.add(user)
                db.flush()
            users[data["email"]] = user
        db.commit()

        activity_data = [
            ("alice@example.com", seeded_products[0].id, "VIEW"),
            ("alice@example.com", seeded_products[1].id, "SEARCH")
        ]
        for email, product_id, activity_type in activity_data:
            existing_activity = db.query(UserActivity).filter(
                UserActivity.user_id == users[email].id,
                UserActivity.product_id == product_id,
                UserActivity.activity_type == activity_type
            ).first()
            if existing_activity is None:
                db.add(UserActivity(
                    user_id=users[email].id,
                    product_id=product_id,
                    activity_type=activity_type,
                    created_at=datetime.utcnow()
                ))
        db.commit()

        print("Ensured sample users and interaction activities.")
        print("Data seeding completed successfully!")

    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
