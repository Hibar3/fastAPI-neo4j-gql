import asyncio
from neo4j import AsyncGraphDatabase
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Neo4j connection details
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "pools-horizon-escape")

print(f"Connecting to: {NEO4J_URI}")
print(f"User: {NEO4J_USER}")
print(f"Password: {NEO4J_PASSWORD}")

async def test_connection():
    try:
        # Try with authentication
        driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        
        async with driver.session() as session:
            # Test a simple query
            result = await session.run("RETURN 1 as test")
            record = await result.single()
            print(f"✅ Connection successful! Test result: {record['test']}")
            
            # Test if we can access the database
            result = await session.run("SHOW DATABASES")
            databases = [record["name"] async for record in result]
            print(f"Available databases: {databases}")
            
    except Exception as e:
        print(f"❌ Connection failed with auth: {e}")
        
        try:
            # Try without authentication
            print("Trying without authentication...")
            driver = AsyncGraphDatabase.driver(NEO4J_URI)
            
            async with driver.session() as session:
                result = await session.run("RETURN 1 as test")
                record = await result.single()
                print(f"✅ Connection successful without auth! Test result: {record['test']}")
                
        except Exception as e2:
            print(f"❌ Connection failed without auth: {e2}")
    
    finally:
        if 'driver' in locals():
            await driver.close()

if __name__ == "__main__":
    asyncio.run(test_connection()) 