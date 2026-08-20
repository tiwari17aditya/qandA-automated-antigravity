import psycopg2
from config import DATABASE_URL

def get_db_connection():
    """Returns a new psycopg2 database connection."""
    return psycopg2.connect(DATABASE_URL, connect_timeout=15)

def init_and_migrate_db():
    """
    Initializes PostgreSQL tables and automatically applies schema migrations.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Base daily_tests table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_tests (
            test_id VARCHAR(50) PRIMARY KEY,
            test_date DATE UNIQUE,
            questions_json JSONB,
            evaluated BOOLEAN DEFAULT FALSE,
            score INTEGER DEFAULT 0,
            total_questions INTEGER DEFAULT 15,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    # Auto-migration for daily_tests: add extra analysis columns if not present
    cursor.execute("""
        ALTER TABLE daily_tests ADD COLUMN IF NOT EXISTS topics TEXT;
        ALTER TABLE daily_tests ADD COLUMN IF NOT EXISTS user_answers_json JSONB;
        ALTER TABLE daily_tests ADD COLUMN IF NOT EXISTS breakdown_json JSONB;
        ALTER TABLE daily_tests ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'PENDING';
        ALTER TABLE daily_tests ADD COLUMN IF NOT EXISTS percentage FLOAT DEFAULT 0.0;
        ALTER TABLE daily_tests ADD COLUMN IF NOT EXISTS evaluated_at TIMESTAMP;
    """)

    # 2. Topic Stats table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS topic_stats (
            topic VARCHAR(100) PRIMARY KEY,
            attempted INTEGER DEFAULT 0,
            correct INTEGER DEFAULT 0,
            accuracy FLOAT DEFAULT 0.0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cursor.execute("""
        ALTER TABLE topic_stats ADD COLUMN IF NOT EXISTS accuracy FLOAT DEFAULT 0.0;
    """)

    # 3. Weekly Reports table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS weekly_reports (
            week_id VARCHAR(50) PRIMARY KEY,
            start_date DATE,
            end_date DATE,
            tests_assigned INTEGER DEFAULT 0,
            tests_completed INTEGER DEFAULT 0,
            tests_absent INTEGER DEFAULT 0,
            total_score INTEGER DEFAULT 0,
            total_possible INTEGER DEFAULT 0,
            overall_percentage FLOAT DEFAULT 0.0,
            summary_json JSONB,
            ai_recommendations TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    cursor.close()
    conn.close()

def mark_expired_tests_absent():
    """
    Finds any unsubmitted tests from past dates (test_date < today)
    that are still 'PENDING' and marks them as 'ABSENT' with score 0.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""
        UPDATE daily_tests
        SET status = 'ABSENT',
            evaluated = TRUE,
            score = 0,
            percentage = 0.0,
            evaluated_at = CURRENT_TIMESTAMP
        WHERE test_date < CURRENT_DATE
          AND evaluated = FALSE
          AND (status = 'PENDING' OR status IS NULL);
    """)
    absent_count = cursor.rowcount
    conn.commit()
    cursor.close()
    conn.close()
    return absent_count

def get_previous_test_data(current_date=None):
    """
    Retrieves the most recent prior test record from daily_tests
    (i.e., test_date < current_date or CURRENT_DATE).
    Returns dict or None.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if current_date:
        cursor.execute("""
            SELECT test_date, topics, status, score, total_questions, 
                   percentage, questions_json, user_answers_json, breakdown_json
            FROM daily_tests
            WHERE test_date < %s
            ORDER BY test_date DESC
            LIMIT 1;
        """, (current_date,))
    else:
        cursor.execute("""
            SELECT test_date, topics, status, score, total_questions, 
                   percentage, questions_json, user_answers_json, breakdown_json
            FROM daily_tests
            WHERE test_date < CURRENT_DATE
            ORDER BY test_date DESC
            LIMIT 1;
        """)
    
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not row:
        return None
        
    return {
        "test_date": str(row[0]),
        "topics": row[1] or "General Mix",
        "status": row[2] or "UNKNOWN",
        "score": row[3] or 0,
        "total_questions": row[4] or 15,
        "percentage": row[5] or 0.0,
        "questions": row[6] or [],
        "user_answers": row[7] or [],
        "breakdown": row[8] or [],
    }

