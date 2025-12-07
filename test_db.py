import mysql.connector
import toml # You might need to pip install toml

# Load secrets manually for testing
secrets = toml.load(".streamlit/secrets.toml")

print("Attempting to connect...")
print(f"Host: {secrets['mysql']['host']}")
print(f"User: {secrets['mysql']['user']}")

try:
    conn = mysql.connector.connect(
        host=secrets["mysql"]["host"],
        user=secrets["mysql"]["user"],
        password=secrets["mysql"]["password"],
        database=secrets["mysql"]["database"],
        port=secrets["mysql"]["port"]
    )
    print("✅ SUCCESS! Connected to database.")
    conn.close()
except Exception as e:
    print("\n❌ FAILED.")
    print(f"Error Message: {e}")
