import os
import psycopg2
from psycopg2.extras import execute_values
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv
from tqdm import tqdm
import time

load_dotenv()

# OpenAI Embeddings 초기화
embeddings_model = OpenAIEmbeddings(model="text-embedding-3-small")

def get_db_connection():
    """데이터베이스 연결 생성"""
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        database=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

def generate_film_embeddings():
    """영화 데이터 임베딩 생성 및 저장"""
    print("\n=== Generating Film Embeddings ===")
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 영화 데이터 조회 (제목 + 설명 + 카테고리)
    query = """
        SELECT 
            f.film_id,
            f.title,
            f.description,
            c.name as category,
            f.release_year,
            f.rating
        FROM film f
        LEFT JOIN film_category fc ON f.film_id = fc.film_id
        LEFT JOIN category c ON fc.category_id = c.category_id
        ORDER BY f.film_id
    """
    cur.execute(query)
    films = cur.fetchall()
    
    print(f"Found {len(films)} films to process")
    
    embeddings_data = []
    batch_size = 100
    
    for i in tqdm(range(0, len(films), batch_size), desc="Processing films"):
        batch = films[i:i+batch_size]
        texts = []
        film_ids = []
        
        for film in batch:
            film_id, title, description, category, year, rating = film
            # 텍스트 구성: 제목, 설명, 카테고리, 연도, 등급
            content = f"Title: {title}\nDescription: {description}\nCategory: {category or 'Unknown'}\nYear: {year}\nRating: {rating}"
            texts.append(content)
            film_ids.append((film_id, content))
        
        # 배치 임베딩 생성
        try:
            batch_embeddings = embeddings_model.embed_documents(texts)
            
            for (film_id, content), embedding in zip(film_ids, batch_embeddings):
                embeddings_data.append((film_id, content, embedding))
            
            time.sleep(0.1)  # API rate limit 방지
        except Exception as e:
            print(f"Error processing batch: {e}")
            continue
    
    # 데이터베이스에 저장
    print("Saving film embeddings to database...")
    execute_values(
        cur,
        "INSERT INTO film_embeddings (film_id, content, embedding) VALUES %s ON CONFLICT (film_id) DO UPDATE SET content = EXCLUDED.content, embedding = EXCLUDED.embedding",
        embeddings_data
    )
    
    conn.commit()
    cur.close()
    conn.close()
    print(f"✓ Saved {len(embeddings_data)} film embeddings")

def generate_actor_embeddings():
    """배우 데이터 임베딩 생성 및 저장"""
    print("\n=== Generating Actor Embeddings ===")
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 배우 데이터 조회 (이름 + 출연 영화 목록)
    query = """
        SELECT 
            a.actor_id,
            a.first_name || ' ' || a.last_name as actor_name,
            STRING_AGG(f.title, ', ') as films
        FROM actor a
        LEFT JOIN film_actor fa ON a.actor_id = fa.actor_id
        LEFT JOIN film f ON fa.film_id = f.film_id
        GROUP BY a.actor_id, actor_name
        ORDER BY a.actor_id
    """
    cur.execute(query)
    actors = cur.fetchall()
    
    print(f"Found {len(actors)} actors to process")
    
    embeddings_data = []
    batch_size = 100
    
    for i in tqdm(range(0, len(actors), batch_size), desc="Processing actors"):
        batch = actors[i:i+batch_size]
        texts = []
        actor_ids = []
        
        for actor in batch:
            actor_id, actor_name, films = actor
            # 텍스트 구성: 배우 이름 + 출연 영화
            content = f"Actor: {actor_name}\nFilms: {films or 'No films'}"
            texts.append(content)
            actor_ids.append((actor_id, content))
        
        # 배치 임베딩 생성
        try:
            batch_embeddings = embeddings_model.embed_documents(texts)
            
            for (actor_id, content), embedding in zip(actor_ids, batch_embeddings):
                embeddings_data.append((actor_id, content, embedding))
            
            time.sleep(0.1)
        except Exception as e:
            print(f"Error processing batch: {e}")
            continue
    
    # 데이터베이스에 저장
    print("Saving actor embeddings to database...")
    execute_values(
        cur,
        "INSERT INTO actor_embeddings (actor_id, content, embedding) VALUES %s ON CONFLICT (actor_id) DO UPDATE SET content = EXCLUDED.content, embedding = EXCLUDED.embedding",
        embeddings_data
    )
    
    conn.commit()
    cur.close()
    conn.close()
    print(f"✓ Saved {len(embeddings_data)} actor embeddings")

def generate_customer_embeddings():
    """고객 데이터 임베딩 생성 및 저장"""
    print("\n=== Generating Customer Embeddings ===")
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 고객 데이터 조회 (이름 + 이메일 + 주소 + 대여 이력)
    query = """
        SELECT 
            c.customer_id,
            c.first_name || ' ' || c.last_name as customer_name,
            c.email,
            a.address,
            ci.city,
            co.country,
            COUNT(r.rental_id) as rental_count
        FROM customer c
        LEFT JOIN address a ON c.address_id = a.address_id
        LEFT JOIN city ci ON a.city_id = ci.city_id
        LEFT JOIN country co ON ci.country_id = co.country_id
        LEFT JOIN rental r ON c.customer_id = r.customer_id
        GROUP BY c.customer_id, customer_name, c.email, a.address, ci.city, co.country
        ORDER BY c.customer_id
    """
    cur.execute(query)
    customers = cur.fetchall()
    
    print(f"Found {len(customers)} customers to process")
    
    embeddings_data = []
    batch_size = 100
    
    for i in tqdm(range(0, len(customers), batch_size), desc="Processing customers"):
        batch = customers[i:i+batch_size]
        texts = []
        customer_ids = []
        
        for customer in batch:
            customer_id, name, email, address, city, country, rental_count = customer
            # 텍스트 구성: 고객 정보 + 대여 횟수
            content = f"Customer: {name}\nEmail: {email}\nLocation: {address}, {city}, {country}\nTotal Rentals: {rental_count}"
            texts.append(content)
            customer_ids.append((customer_id, content))
        
        # 배치 임베딩 생성
        try:
            batch_embeddings = embeddings_model.embed_documents(texts)
            
            for (customer_id, content), embedding in zip(customer_ids, batch_embeddings):
                embeddings_data.append((customer_id, content, embedding))
            
            time.sleep(0.1)
        except Exception as e:
            print(f"Error processing batch: {e}")
            continue
    
    # 데이터베이스에 저장
    print("Saving customer embeddings to database...")
    execute_values(
        cur,
        "INSERT INTO customer_embeddings (customer_id, content, embedding) VALUES %s ON CONFLICT (customer_id) DO UPDATE SET content = EXCLUDED.content, embedding = EXCLUDED.embedding",
        embeddings_data
    )
    
    conn.commit()
    cur.close()
    conn.close()
    print(f"✓ Saved {len(embeddings_data)} customer embeddings")

def generate_category_embeddings():
    """카테고리 데이터 임베딩 생성 및 저장"""
    print("\n=== Generating Category Embeddings ===")
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 카테고리 데이터 조회 (카테고리명 + 영화 목록)
    query = """
        SELECT 
            c.category_id,
            c.name as category_name,
            COUNT(fc.film_id) as film_count,
            STRING_AGG(f.title, ', ' ORDER BY f.title) as films
        FROM category c
        LEFT JOIN film_category fc ON c.category_id = fc.category_id
        LEFT JOIN film f ON fc.film_id = f.film_id
        GROUP BY c.category_id, c.name
        ORDER BY c.category_id
    """
    cur.execute(query)
    categories = cur.fetchall()
    
    print(f"Found {len(categories)} categories to process")
    
    embeddings_data = []
    texts = []
    category_ids = []
    
    for category in categories:
        category_id, name, film_count, films = category
        # 텍스트 구성: 카테고리명 + 영화 수 + 영화 목록 (일부)
        films_preview = films[:500] if films else "No films"  # 처음 500자만
        content = f"Category: {name}\nFilm Count: {film_count}\nFilms: {films_preview}"
        texts.append(content)
        category_ids.append((category_id, content))
    
    # 임베딩 생성
    try:
        print("Generating embeddings...")
        batch_embeddings = embeddings_model.embed_documents(texts)
        
        for (category_id, content), embedding in zip(category_ids, batch_embeddings):
            embeddings_data.append((category_id, content, embedding))
    except Exception as e:
        print(f"Error generating embeddings: {e}")
        return
    
    # 데이터베이스에 저장
    print("Saving category embeddings to database...")
    execute_values(
        cur,
        "INSERT INTO category_embeddings (category_id, content, embedding) VALUES %s ON CONFLICT (category_id) DO UPDATE SET content = EXCLUDED.content, embedding = EXCLUDED.embedding",
        embeddings_data
    )
    
    conn.commit()
    cur.close()
    conn.close()
    print(f"✓ Saved {len(embeddings_data)} category embeddings")

def generate_unified_embeddings():
    """통합 임베딩 테이블 생성 (모든 데이터를 하나의 테이블에)"""
    print("\n=== Generating Unified Embeddings ===")
    conn = get_db_connection()
    cur = conn.cursor()
    
    # 기존 통합 임베딩 삭제
    cur.execute("DELETE FROM unified_embeddings")
    
    # Film embeddings 복사
    print("Copying film embeddings...")
    cur.execute("""
        INSERT INTO unified_embeddings (source_table, source_id, content, embedding, metadata)
        SELECT 
            'film' as source_table,
            film_id as source_id,
            content,
            embedding,
            jsonb_build_object('type', 'film') as metadata
        FROM film_embeddings
    """)
    
    # Actor embeddings 복사
    print("Copying actor embeddings...")
    cur.execute("""
        INSERT INTO unified_embeddings (source_table, source_id, content, embedding, metadata)
        SELECT 
            'actor' as source_table,
            actor_id as source_id,
            content,
            embedding,
            jsonb_build_object('type', 'actor') as metadata
        FROM actor_embeddings
    """)
    
    # Customer embeddings 복사
    print("Copying customer embeddings...")
    cur.execute("""
        INSERT INTO unified_embeddings (source_table, source_id, content, embedding, metadata)
        SELECT 
            'customer' as source_table,
            customer_id as source_id,
            content,
            embedding,
            jsonb_build_object('type', 'customer') as metadata
        FROM customer_embeddings
    """)
    
    # Category embeddings 복사
    print("Copying category embeddings...")
    cur.execute("""
        INSERT INTO unified_embeddings (source_table, source_id, content, embedding, metadata)
        SELECT 
            'category' as source_table,
            category_id as source_id,
            content,
            embedding,
            jsonb_build_object('type', 'category') as metadata
        FROM category_embeddings
    """)
    
    conn.commit()
    
    # 통계 출력
    cur.execute("SELECT COUNT(*) FROM unified_embeddings")
    total_count = cur.fetchone()[0]
    
    cur.close()
    conn.close()
    print(f"✓ Created unified embeddings table with {total_count} entries")

def main():
    """모든 임베딩 생성 실행"""
    print("\n" + "="*50)
    print("DVD Rental Database - Embedding Generation")
    print("="*50)
    
    try:
        # 각 테이블별 임베딩 생성
        generate_film_embeddings()
        generate_actor_embeddings()
        generate_customer_embeddings()
        generate_category_embeddings()
        
        # 통합 임베딩 테이블 생성
        generate_unified_embeddings()
        
        print("\n" + "="*50)
        print("✓ All embeddings generated successfully!")
        print("="*50)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()