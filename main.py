import strawberry
from pathlib import Path
from strawberry.schema.config import StrawberryConfig
from fastapi import FastAPI
from strawberry.fastapi import GraphQLRouter
from neo4j import AsyncGraphDatabase
from typing import List, Optional
import os
from dotenv import load_dotenv

# Load environment variables (e.g., Neo4j credentials)
load_dotenv()

# Neo4j connection
def get_driver():
    NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
    try:
        driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        print("✅ Neo4j driver created with authentication")
        return driver
    except Exception as e:
        print(f"❌ Failed to create driver with auth: {e}")
        driver = AsyncGraphDatabase.driver(NEO4J_URI)
        print("✅ Neo4j driver created without authentication")
        return driver

driver = get_driver()

# Load schema.graphql
type_defs = (Path(__file__).parent / "schema.graphql").read_text()

# async def init_sample_data():
#     """Initialize sample data if database is empty"""
#     try:
#         async with driver.session() as session:
#             # Check if we have any movies
#             result = await session.run("MATCH (m:Movie) RETURN count(m) as count")
#             record = await result.single()
#             if record["count"] == 0:
#                 print("📝 Initializing sample data...")
#                 # Create sample movies and actors
#                 await session.run("""
#                     CREATE (m1:Movie {title: 'The Matrix', released: 1999})
#                     CREATE (m2:Movie {title: 'The Matrix Reloaded', released: 2003})
#                     CREATE (p1:Person {name: 'Keanu Reeves'})
#                     CREATE (p2:Person {name: 'Laurence Fishburne'})
#                     CREATE (p1)-[:ACTED_IN]->(m1)
#                     CREATE (p1)-[:ACTED_IN]->(m2)
#                     CREATE (p2)-[:ACTED_IN]->(m1)
#                     CREATE (p2)-[:ACTED_IN]->(m2)
#                 """)
#                 print("✅ Sample data created!")
#             else:
#                 print(f"📊 Found {record['count']} existing movies")
#     except Exception as e:
#         print(f"⚠️ Could not initialize sample data: {e}")

# # Initialize sample data on startup
# import asyncio
# try:
#     asyncio.create_task(init_sample_data())
# except Exception as e:
#     print(f"⚠️ Could not schedule sample data initialization: {e}")

# GraphQL Types
@strawberry.type
class Genre:
    name: str = strawberry.field()

    @strawberry.field
    async def movies(self) -> List['Movie']:
        async with driver.session() as session:
            result = await session.run(
                "MATCH (g:Genre {name: $name})<-[:IN_GENRE]-(m:Movie) RETURN elementId(m) AS movieId, m.title AS title, m.released AS released, m.tagline AS tagline",
                name=self.name
            )
            movies = []
            async for record in result:
                print(f"[DEBUG] Genre.movies raw record: {record}")
                try:
                    movie = Movie(
                        movieId=record.get("movieId", ""),
                        title=record.get("title", ""),
                        released=record.get("released"),
                        tagline=record.get("tagline")
                    )
                    print(f"[DEBUG] Genre.movies Movie args: movieId={movie.movieId}, title={movie.title}, released={movie.released}, tagline={movie.tagline}")
                    movies.append(movie)
                except Exception as e:
                    print(f"[ERROR] Genre.movies Movie instantiation failed: {e}")
            return movies

@strawberry.type
class Movie:
    movieId: strawberry.ID = strawberry.field()
    title: str = strawberry.field()
    released: Optional[int] = strawberry.field(default=None)
    tagline: Optional[str] = strawberry.field(default=None)

    @strawberry.field
    async def genres(self) -> List[Genre]:
        async with driver.session() as session:
            result = await session.run(
                "MATCH (m:Movie {title: $title})-[:IN_GENRE]->(g:Genre) RETURN g.name AS name",
                title=self.title
            )
            genres = []
            async for record in result:
                print(f"[DEBUG] Movie.genres raw record: {record}")
                try:
                    genre = Genre(name=record.get("name", ""))
                    print(f"[DEBUG] Movie.genres Genre args: name={genre.name}")
                    genres.append(genre)
                except Exception as e:
                    print(f"[ERROR] Movie.genres Genre instantiation failed: {e}")
            return genres

    @strawberry.field
    async def actors(self) -> List['Person']:
        async with driver.session() as session:
            result = await session.run(
                "MATCH (p:Person)-[:ACTED_IN]->(m:Movie {title: $title}) RETURN elementId(p) AS personId, p.name AS name, p.born AS born",
                title=self.title
            )
            people = []
            async for record in result:
                print(f"[DEBUG] Movie.actors raw record: {record}")
                try:
                    person = Person(
                        personId=record.get("personId", ""),
                        name=record.get("name", ""),
                        born=record.get("born")
                    )
                    print(f"[DEBUG] Movie.actors Person args: personId={person.personId}, name={person.name}, born={person.born}")
                    people.append(person)
                except Exception as e:
                    print(f"[ERROR] Movie.actors Person instantiation failed: {e}")
            return people

    @strawberry.field
    async def similar(self) -> List['Movie']:
        query = """
        MATCH (m:Movie {title: $title})-[:IN_GENRE]->(g:Genre)
        WITH m, collect(id(g)) AS m1Genres
        MATCH (n:Movie)-[:IN_GENRE]->(g:Genre) 
        WHERE n <> m
        WITH m, m1Genres, n, collect(id(g)) AS m2Genres
        RETURN elementId(n) AS movieId, n.title AS title, n.released AS released, n.tagline AS tagline,
               gds.similarity.jaccard(m1Genres, m2Genres) AS similarity
        ORDER BY similarity DESC
        LIMIT 10
        """
        async with driver.session() as session:
            result = await session.run(query, title=self.title)
            movies = []
            async for record in result:
                print(f"[DEBUG] Movie.similar raw record: {record}")
                try:
                    movie = Movie(
                        movieId=record.get("movieId", ""),
                        title=record.get("title", ""),
                        released=record.get("released"),
                        tagline=record.get("tagline")
                    )
                    print(f"[DEBUG] Movie.similar Movie args: movieId={movie.movieId}, title={movie.title}, released={movie.released}, tagline={movie.tagline}")
                    movies.append(movie)
                except Exception as e:
                    print(f"[ERROR] Movie.similar Movie instantiation failed: {e}")
            return movies

@strawberry.type
class Person:
    personId: strawberry.ID = strawberry.field()
    name: str = strawberry.field()
    born: Optional[int] = strawberry.field(default=None)

    @strawberry.field
    async def actedIn(self) -> List[Movie]:
        async with driver.session() as session:
            result = await session.run(
                "MATCH (p:Person {name: $name})-[:ACTED_IN]->(m:Movie) RETURN elementId(m) AS movieId, m.title AS title, m.released AS released, m.tagline AS tagline",
                name=self.name
            )
            movies = []
            async for record in result:
                print(f"[DEBUG] Person.actedIn raw record: {record}")
                try:
                    movie = Movie(
                        movieId=record.get("movieId", ""),
                        title=record.get("title", ""),
                        released=record.get("released"),
                        tagline=record.get("tagline")
                    )
                    print(f"[DEBUG] Person.actedIn Movie args: movieId={movie.movieId}, title={movie.title}, released={movie.released}, tagline={movie.tagline}")
                    movies.append(movie)
                except Exception as e:
                    print(f"[ERROR] Person.actedIn Movie instantiation failed: {e}")
            return movies

# Query Type
@strawberry.type
class Query:
    @strawberry.field
    async def movies(self) -> List[Movie]:
        async with driver.session() as session:
            result = await session.run(
                "MATCH (m:Movie) RETURN elementId(m) AS movieId, m.title AS title, m.released AS released, m.tagline AS tagline"
            )
            movies = []
            async for record in result:
                print(f"[DEBUG] Query.movies raw record: {record}")
                try:
                    movie = Movie(
                        movieId=record.get("movieId", ""),
                        title=record.get("title", ""),
                        released=record.get("released"),
                        tagline=record.get("tagline")
                    )
                    print(f"[DEBUG] Query.movies Movie args: movieId={movie.movieId}, title={movie.title}, released={movie.released}, tagline={movie.tagline}")
                    movies.append(movie)
                except Exception as e:
                    print(f"[ERROR] Query.movies Movie instantiation failed: {e}")
            return movies

    @strawberry.field
    async def movie(self, movieId: strawberry.ID) -> Optional[Movie]:
        async with driver.session() as session:
            result = await session.run(
                "MATCH (m:Movie) WHERE elementId(m) = $movieId RETURN elementId(m) AS movieId, m.title AS title, m.released AS released, m.tagline AS tagline",
                movieId=movieId
            )
            record = await result.single()
            print(f"[DEBUG] Query.movie raw record: {record}")
            if record:
                try:
                    movie = Movie(
                        movieId=record.get("movieId", ""),
                        title=record.get("title", ""),
                        released=record.get("released"),
                        tagline=record.get("tagline")
                    )
                    print(f"[DEBUG] Query.movie Movie args: movieId={movie.movieId}, title={movie.title}, released={movie.released}, tagline={movie.tagline}")
                    return movie
                except Exception as e:
                    print(f"[ERROR] Query.movie Movie instantiation failed: {e}")
            return None

    @strawberry.field
    async def people(self) -> List[Person]:
        async with driver.session() as session:
            result = await session.run(
                "MATCH (p:Person) RETURN elementId(p) AS personId, p.name AS name, p.born AS born"
            )
            people = []
            async for record in result:
                print(f"[DEBUG] Query.people raw record: {record}")
                try:
                    person = Person(
                        personId=record.get("personId", ""),
                        name=record.get("name", ""),
                        born=record.get("born")
                    )
                    print(f"[DEBUG] Query.people Person args: personId={person.personId}, name={person.name}, born={person.born}")
                    people.append(person)
                except Exception as e:
                    print(f"[ERROR] Query.people Person instantiation failed: {e}")
            return people

    @strawberry.field
    async def person(self, personId: strawberry.ID) -> Optional[Person]:
        async with driver.session() as session:
            result = await session.run(
                "MATCH (p:Person) WHERE elementId(p) = $personId RETURN elementId(p) AS personId, p.name AS name, p.born AS born",
                personId=personId
            )
            record = await result.single()
            print(f"[DEBUG] Query.person raw record: {record}")
            if record:
                try:
                    person = Person(
                        personId=record.get("personId", ""),
                        name=record.get("name", ""),
                        born=record.get("born")
                    )
                    print(f"[DEBUG] Query.person Person args: personId={person.personId}, name={person.name}, born={person.born}")
                    return person
                except Exception as e:
                    print(f"[ERROR] Query.person Person instantiation failed: {e}")
            return None

    @strawberry.field
    async def genres(self) -> List[Genre]:
        async with driver.session() as session:
            result = await session.run(
                "MATCH (g:Genre) RETURN g.name AS name"
            )
            genres = []
            async for record in result:
                print(f"[DEBUG] Query.genres raw record: {record}")
                try:
                    genre = Genre(name=record.get("name", ""))
                    print(f"[DEBUG] Query.genres Genre args: name={genre.name}")
                    genres.append(genre)
                except Exception as e:
                    print(f"[ERROR] Query.genres Genre instantiation failed: {e}")
            return genres

    @strawberry.field
    async def genre(self, name: str) -> Optional[Genre]:
        async with driver.session() as session:
            result = await session.run(
                "MATCH (g:Genre {name: $name}) RETURN g.name AS name",
                name=name
            )
            record = await result.single()
            print(f"[DEBUG] Query.genre raw record: {record}")
            if record:
                try:
                    genre = Genre(name=record.get("name", ""))
                    print(f"[DEBUG] Query.genre Genre args: name={genre.name}")
                    return genre
                except Exception as e:
                    print(f"[ERROR] Query.genre Genre instantiation failed: {e}")
            return None

# Schema and FastAPI setup
schema = strawberry.Schema(
    query=Query,
    config=StrawberryConfig(auto_camel_case=False)
)

app = FastAPI()
graphql_app = GraphQLRouter(schema)
app.include_router(graphql_app, prefix="/graphql")