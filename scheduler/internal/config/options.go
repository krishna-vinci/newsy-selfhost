package config

import (
	"log/slog"
	"os"
	"strconv"
	"time"
)

type Options struct {
	// Database
	DBHost     string
	DBPort     string
	DBUser     string
	DBPassword string
	DBName     string

	// Python Backend
	PythonBackendURL string

	// Worker Pool
	WorkerPoolSize int

	// Scheduling
	PollingFrequency      time.Duration
	BatchSize             int
	PollingErrorLimit     int
	PollingLimitPerHost   int
	CleanupFrequency      time.Duration

	// Server
	ServerPort string
	LogLevel   string
}

var Opts *Options

func InitOptions() {
	Opts = &Options{
		DBHost:              getEnv("DB_HOST", "localhost"),
		DBPort:              getEnv("DB_PORT", "5432"),
		DBUser:              getEnv("DB_USER", "postgres"),
		DBPassword:          getEnv("DB_PASSWORD", ""),
		DBName:              getEnv("DB_NAME", "newsy"),
		PythonBackendURL:    getEnv("PYTHON_BACKEND_URL", "http://localhost:8765"),
		WorkerPoolSize:      getEnvInt("WORKER_POOL_SIZE", 16),
		PollingFrequency:    getEnvDuration("POLLING_FREQUENCY", "5m"),
		BatchSize:           getEnvInt("BATCH_SIZE", 100),
		PollingErrorLimit:   getEnvInt("POLLING_ERROR_LIMIT", 10),
		PollingLimitPerHost: getEnvInt("POLLING_LIMIT_PER_HOST", 5),
		CleanupFrequency:    getEnvDuration("CLEANUP_FREQUENCY", "24h"),
		ServerPort:          getEnv("SERVER_PORT", "8667"),
		LogLevel:            getEnv("LOG_LEVEL", "info"),
	}

	slog.Info("Configuration loaded",
		slog.String("db_host", Opts.DBHost),
		slog.Int("worker_pool_size", Opts.WorkerPoolSize),
		slog.Duration("polling_frequency", Opts.PollingFrequency),
		slog.Int("batch_size", Opts.BatchSize),
	)
}

func getEnv(key, defaultValue string) string {
	value := os.Getenv(key)
	if value == "" {
		return defaultValue
	}
	return value
}

func getEnvInt(key string, defaultValue int) int {
	value := os.Getenv(key)
	if value == "" {
		return defaultValue
	}
	intValue, err := strconv.Atoi(value)
	if err != nil {
		slog.Warn("Invalid integer value for env var, using default",
			slog.String("key", key),
			slog.String("value", value),
			slog.Int("default", defaultValue),
		)
		return defaultValue
	}
	return intValue
}

func getEnvDuration(key, defaultValue string) time.Duration {
	value := os.Getenv(key)
	if value == "" {
		value = defaultValue
	}
	duration, err := time.ParseDuration(value)
	if err != nil {
		slog.Warn("Invalid duration value for env var, using default",
			slog.String("key", key),
			slog.String("value", value),
			slog.String("default", defaultValue),
		)
		duration, _ = time.ParseDuration(defaultValue)
	}
	return duration
}
