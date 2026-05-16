-- Add job descriptions so interviews can be designed from the pasted role requirements.
ALTER TABLE interviews
    ADD COLUMN IF NOT EXISTS job_description TEXT DEFAULT '';
