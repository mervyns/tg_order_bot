# scripts/check_remote_db.py
import os
import sys
import psycopg2
from urllib.parse import urlparse
from dotenv import load_dotenv
from pathlib import Path

def load_environment():
    """Load environment variables properly"""
    env_path = Path(__file__).parent.parent / '.env'
    print(f"Loading .env from: {env_path.absolute()}")
    
    # Clear existing environment variable to avoid any cached values
    if 'DATABASE_URL' in os.environ:
        del os.environ['DATABASE_URL']
    
    # Load the .env file
    success = load_dotenv(env_path, override=True)
    if not success:
        print("Failed to load .env file")
        return False
    
    return True

def print_env_debug():
    """Print environment file contents and loaded variables"""
    env_path = Path(__file__).parent.parent / '.env'
    
    print("\n=== Environment File Debug ===")
    print(f"Looking for .env file at: {env_path}")
    
    if env_path.exists():
        print("\nContent of .env file:")
        with open(env_path, 'r') as f:
            for line in f:
                if 'password' in line.lower():
                    key, value = line.strip().split('=', 1)
                    print(f"{key}=********")
                else:
                    print(line.strip())
    else:
        print("\n.env file not found!")
    
    database_url = os.getenv('DATABASE_URL')
    print("\nActual loaded DATABASE_URL:", database_url)

def test_remote_connection():
    """Test connection to remote PostgreSQL server"""
    if not load_environment():
        print("Failed to load environment variables")
        return False
    
    # Debug environment setup
    print_env_debug()
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("\nERROR: DATABASE_URL is not set in .env file")
        return False
        
    print("\nTesting connection to remote database...")
    
    # Print the URL with masked password
    url_parts = urlparse(database_url)
    masked_url = database_url.replace(url_parts.password, '********') if url_parts.password else database_url
    print(f"Database URL: {masked_url}")
    
    try:
        # Parse the database URL
        url = urlparse(database_url)
        
        # Extract connection parameters
        db_info = {
            'dbname': url.path[1:],  # Remove leading slash
            'user': url.username,
            'password': url.password,
            'host': url.hostname,
            'port': url.port or 5432
        }
        
        print(f"\nConnection details:")
        print(f"Host: {db_info['host']}")
        print(f"Port: {db_info['port']}")
        print(f"Database: {db_info['dbname']}")
        print(f"User: {db_info['user']}")
        print(f"Password: {'*' * 8}")
        
        # Validate connection parameters
        missing_params = [k for k, v in db_info.items() if not v]
        if missing_params:
            print(f"\n❌ Missing connection parameters: {', '.join(missing_params)}")
            return False
        
        # Try to connect
        print("\nAttempting connection...")
        conn = psycopg2.connect(**db_info)
        
        # Get server version
        cur = conn.cursor()
        cur.execute('SELECT version();')
        version = cur.fetchone()[0]
        print(f"\nSuccessfully connected to PostgreSQL!")
        print(f"Server version: {version}")
        
        # Check if we can create tables (test permissions)
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS connection_test (
                    id serial PRIMARY KEY,
                    test_column varchar(50)
                );
            """)
            print("✅ Database permissions verified (can create tables)")
            
            # Clean up test table
            cur.execute("DROP TABLE connection_test;")
            conn.commit()
        except psycopg2.Error as e:
            print(f"⚠️  Limited permissions detected: {str(e)}")
        
        # Close connection
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"\n❌ Connection failed: {str(e)}")
        print("\nTroubleshooting steps:")
        print("1. Verify the remote server address and port are correct")
        print("2. Check if the remote server allows connections from your IP")
        print("3. Verify your username and password")
        print("4. Make sure the database exists and you have access to it")
        print("\nCommon issues:")
        print("- Firewall blocking port 5432")
        print("- pg_hba.conf not configured to accept remote connections")
        print("- Invalid credentials")
        print("- Database doesn't exist")
        
        # Additional debugging information
        print("\nDebug Information:")
        print(f"Python version: {sys.version}")
        print(f"psycopg2 version: {psycopg2.__version__}")
        return False

def verify_env_file():
    """Verify and fix .env file if needed"""
    env_path = Path(__file__).parent.parent / '.env'
    
    # if not env_path.exists():
    #     print("\nCreating new .env file...")
    #     with open(env_path, 'w') as f:
    #         f.write("DATABASE_URL=postgresql+asyncpg://username:password@host:5432/dbname\n")
    #     print("Created .env file template. Please update with your actual database credentials.")
    #     return False
    
    # Check if file is readable
    try:
        with open(env_path, 'r') as f:
            content = f.read()
            if 'DATABASE_URL' not in content:
                print("\nWarning: DATABASE_URL not found in .env file")
                return False
    except Exception as e:
        print(f"\nError reading .env file: {str(e)}")
        return False
    
    return True

if __name__ == "__main__":
    print("Starting database connection check...")
    
    # Verify environment file
    if not verify_env_file():
        sys.exit(1)
    
    # Test connection
    success = test_remote_connection()
    sys.exit(0 if success else 1)