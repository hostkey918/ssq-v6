CREATE TABLE IF NOT EXISTS draws (
    id SERIAL PRIMARY KEY,
    issue VARCHAR(32) NOT NULL,
    draw_date DATE,
    red1 INTEGER NOT NULL,
    red2 INTEGER NOT NULL,
    red3 INTEGER NOT NULL,
    red4 INTEGER NOT NULL,
    red5 INTEGER NOT NULL,
    red6 INTEGER NOT NULL,
    blue INTEGER NOT NULL,
    source VARCHAR(64) NOT NULL DEFAULT 'cwl',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_draws_issue UNIQUE (issue)
);

CREATE INDEX IF NOT EXISTS ix_draws_issue ON draws (issue);
CREATE INDEX IF NOT EXISTS ix_draws_draw_date ON draws (draw_date);
