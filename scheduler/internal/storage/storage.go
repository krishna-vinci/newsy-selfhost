package storage

import (
	"database/sql"
	"fmt"
	"log/slog"

	_ "github.com/lib/pq"
	"github.com/krishna/newsy-scheduler/internal/config"
)

type Storage struct {
	db *sql.DB
}

func NewStorage() (*Storage, error) {
	connStr := fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=disable",
		config.Opts.DBHost,
		config.Opts.DBPort,
		config.Opts.DBUser,
		config.Opts.DBPassword,
		config.Opts.DBName,
	)

	db, err := sql.Open("postgres", connStr)
	if err != nil {
		return nil, fmt.Errorf("failed to open database: %w", err)
	}

	// Test connection
	if err := db.Ping(); err != nil {
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	// Configure connection pool
	db.SetMaxOpenConns(25)
	db.SetMaxIdleConns(25)

	slog.Info("Database connection established",
		slog.String("host", config.Opts.DBHost),
		slog.String("database", config.Opts.DBName),
	)

	return &Storage{db: db}, nil
}

func (s *Storage) Close() error {
	return s.db.Close()
}

func (s *Storage) NewBatchBuilder() *BatchBuilder {
	return &BatchBuilder{
		db: s.db,
	}
}

// Ensure required columns exist
func (s *Storage) EnsureSchema() error {
	migrations := []string{
		`ALTER TABLE feeds ADD COLUMN IF NOT EXISTS next_check_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()`,
		`ALTER TABLE feeds ADD COLUMN IF NOT EXISTS checked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()`,
		`ALTER TABLE feeds ADD COLUMN IF NOT EXISTS parsing_error_count INTEGER DEFAULT 0`,
		`ALTER TABLE feeds ADD COLUMN IF NOT EXISTS parsing_error_msg TEXT DEFAULT ''`,
	}

	for _, migration := range migrations {
		if _, err := s.db.Exec(migration); err != nil {
			slog.Error("Migration failed", slog.String("sql", migration), slog.Any("error", err))
			return err
		}
	}

	slog.Info("Schema migrations completed successfully")
	return nil
}
