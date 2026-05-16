-- =============================================
-- INTERVUE.AI — Complete Database Schema
-- USED AT SUPABASE SQL EDITOR
-- =============================================

-- Step 1: Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Step 2: Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    hashed_password TEXT,
    plan TEXT DEFAULT 'free' CHECK (plan IN ('free', 'pro', 'enterprise')),
    difficulty_profile TEXT DEFAULT 'beginner'
        CHECK (difficulty_profile IN ('beginner', 'intermediate', 'advanced')),
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Step 3: Resumes table
CREATE TABLE resumes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    file_url TEXT,
    file_name TEXT,
    parsed_json JSONB,
    raw_text TEXT,
    embedding_model TEXT DEFAULT 'gemini-embedding-001',
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Step 4: Resume chunks (RAG vector store)
CREATE TABLE resume_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resume_id UUID REFERENCES resumes(id) ON DELETE CASCADE NOT NULL,
    chunk_text TEXT NOT NULL,
    section_tag TEXT,
    embedding VECTOR(768),
    sha256_hash TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Step 5: HNSW index for fast vector search
CREATE INDEX idx_resume_chunks_embedding
    ON resume_chunks USING hnsw (embedding vector_cosine_ops);

-- Step 6: Composite index for filtered queries
CREATE INDEX idx_resume_chunks_resume_section
    ON resume_chunks (resume_id, section_tag);

-- Step 7: User topic profiles (weakness tracking)
CREATE TABLE user_topic_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    topic TEXT NOT NULL,
    avg_score FLOAT DEFAULT 0,
    attempt_count INT DEFAULT 0,
    last_seen TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, topic)
);

CREATE INDEX idx_utp_user ON user_topic_profiles(user_id);

-- Step 8: Interviews table
CREATE TABLE interviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    resume_id UUID REFERENCES resumes(id) ON DELETE SET NULL,
    job_role TEXT NOT NULL,
    job_description TEXT DEFAULT '',
    interview_mode TEXT DEFAULT 'faang'
        CHECK (interview_mode IN ('faang', 'startup', 'hr')),
    status TEXT DEFAULT 'in_progress'
        CHECK (status IN ('in_progress', 'completed', 'aborted')),
    langgraph_thread_id TEXT,
    overall_score INT,
    total_tokens INT DEFAULT 0,
    behavior_notes JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    completed_at TIMESTAMPTZ
);

-- Step 9: Questions table
CREATE TABLE questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id UUID REFERENCES interviews(id) ON DELETE CASCADE NOT NULL,
    text TEXT NOT NULL,
    category TEXT,
    topic TEXT,
    difficulty TEXT,
    why_asked TEXT,
    is_weakness_focused BOOLEAN DEFAULT false,
    order_idx INT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Step 10: Answers table
CREATE TABLE answers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_id UUID REFERENCES questions(id) ON DELETE CASCADE NOT NULL,
    answer_text TEXT,
    score INT,
    accuracy_score INT,
    clarity_score INT,
    depth_score INT,
    cot_reasoning TEXT,
    rubric_json JSONB,
    speech_pace FLOAT,
    filler_count INT,
    pause_count INT,
    behavior_score INT,
    behavior_notes TEXT,
    tokens_used INT,
    latency_ms INT,
    audio_duration_sec FLOAT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Step 11: Reports table
CREATE TABLE reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id UUID REFERENCES interviews(id) ON DELETE CASCADE NOT NULL UNIQUE,
    overall_score INT,
    grade TEXT,
    interview_readiness TEXT
        CHECK (interview_readiness IN ('not_ready', 'almost_ready', 'ready')),
    feedback_json JSONB,
    improvement_plan JSONB,
    speech_summary JSONB,
    strengths JSONB DEFAULT '[]'::jsonb,
    next_session_focus JSONB DEFAULT '[]'::jsonb,
    pdf_url TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Step 12: AI costs table
CREATE TABLE ai_costs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id UUID REFERENCES interviews(id) ON DELETE SET NULL,
    model TEXT NOT NULL,
    call_type TEXT NOT NULL,
    tokens_in INT DEFAULT 0,
    tokens_out INT DEFAULT 0,
    cost_inr FLOAT DEFAULT 0,
    latency_ms INT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_ai_costs_interview_created
    ON ai_costs (interview_id, created_at DESC);

CREATE INDEX idx_ai_costs_created_at
    ON ai_costs (created_at DESC);

-- Step 13: Prompt templates table
CREATE TABLE prompt_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    version INT DEFAULT 1,
    is_active BOOLEAN DEFAULT true,
    content TEXT NOT NULL,
    eval_score FLOAT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Step 14: User badges (gamification)
CREATE TABLE user_badges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    badge_id TEXT NOT NULL,
    earned_at TIMESTAMPTZ DEFAULT now()
);

-- Step 15: User streaks
CREATE TABLE user_streaks (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    current_streak INT DEFAULT 0,
    longest_streak INT DEFAULT 0,
    last_interview_date DATE
);

-- Step 16: Audit logs (security + anti-cheat)
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    interview_id UUID REFERENCES interviews(id) ON DELETE SET NULL,
    action TEXT NOT NULL,
    ip_address TEXT,
    user_agent TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Step 17: Vector similarity search function
CREATE OR REPLACE FUNCTION match_chunks(
    p_resume_id UUID,
    p_query_embedding VECTOR(768),
    p_match_count INT DEFAULT 10,
    p_section_tag TEXT DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    chunk_text TEXT,
    section_tag TEXT,
    embedding VECTOR(768),
    similarity FLOAT
)
LANGUAGE sql STABLE
AS $$     SELECT
        id, chunk_text, section_tag, embedding,
        1 - (embedding <=> p_query_embedding) AS similarity
    FROM resume_chunks
    WHERE resume_id = p_resume_id
      AND (p_section_tag IS NULL OR section_tag = p_section_tag)
    ORDER BY embedding <=> p_query_embedding
    LIMIT p_match_count;
 $$;

-- Step 18: Upsert topic score function (rolling average)
CREATE OR REPLACE FUNCTION upsert_topic_score(
    p_user_id UUID,
    p_topic TEXT,
    p_new_score FLOAT
)
RETURNS VOID
LANGUAGE plpgsql
AS $$ BEGIN
    INSERT INTO user_topic_profiles (user_id, topic, avg_score, attempt_count, last_seen)
    VALUES (p_user_id, p_topic, p_new_score, 1, now())
    ON CONFLICT (user_id, topic)
    DO UPDATE SET
        avg_score = (user_topic_profiles.avg_score * user_topic_profiles.attempt_count + p_new_score)
                    / (user_topic_profiles.attempt_count + 1),
        attempt_count = user_topic_profiles.attempt_count + 1,
        last_seen = now();
END;
 $$;

-- Step 19: Enable Row Level Security
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE resumes ENABLE ROW LEVEL SECURITY;
ALTER TABLE resume_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE interviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE answers ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_topic_profiles ENABLE ROW LEVEL SECURITY;

-- Step 20: RLS Policies (users can only see their own data)
CREATE POLICY "Users see own data" ON users
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users see own resumes" ON resumes
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users see own interviews" ON interviews
    FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY "Users see own reports" ON reports
    FOR SELECT USING (
        interview_id IN (
            SELECT id FROM interviews WHERE user_id = auth.uid()
        )
    );
